"""Production tiled inference with disk-backed stitching and streamed outputs."""
from pathlib import Path
import json
import shutil
import time
import numpy as np
from PIL import Image
import zarr
from numcodecs import Blosc
from .disk_stitch import DiskStitcher, windows
from .io import canonical_axes, canonical_transforms, write_json
from .inference import render_rgb, combine_masks
from .streaming import read_window, overview_field, sampled_overview, build_pyramid_level
from .stream_measurements import add_streamed


def label_group(output, field, prompt, time_index):
    root = zarr.open_group(str(output),mode='a')
    image = root[field.path] if field.path else root
    container = image.require_group('labels')
    name = 'wevisone_'+prompt.name
    if time_index:
        return container[name]
    group = container.create_group(name)
    height,width = field.cyx_shape[1:]
    datasets = []
    factor = 1
    while True:
        level = str(len(datasets))
        array = group.create_dataset(level,shape=(field.timepoints,1,1,height,width),dtype='u4',
                                     chunks=(1,1,1,min(height,512),min(width,512)),
                                     compressor=Blosc(cname='zstd',clevel=3,shuffle=Blosc.BITSHUFFLE))
        array.attrs['_ARRAY_DIMENSIONS'] = list('tczyx')
        transforms = canonical_transforms(field.multiscale['datasets'][0].get('coordinateTransformations',[]),field.names,factor,label=True)
        if not transforms:
            transforms = [{'type':'scale','scale':[1,1,1,factor,factor]}]
        datasets.append({'path':level,'coordinateTransformations':transforms})
        if max(height,width) <= 256:
            break
        height,width = (height+1)//2,(width+1)//2
        factor *= 2
    ms = {'version':'0.4','name':name,'axes':canonical_axes(field),'datasets':datasets}
    if 'coordinateTransformations' in field.multiscale:
        ms['coordinateTransformations'] = canonical_transforms(field.multiscale['coordinateTransformations'],field.names,label=True)
    group.attrs.update({'multiscales':[ms],'image-label':{'version':'0.4','source':{'image':'../../'}}})
    declared = list(container.attrs.get('labels',[]))
    if name not in declared:
        declared.append(name)
    container.attrs['labels'] = declared
    return group


def segment_frame(predictor, settings, prompts, source_field, field, output, index, time_index, report, measurements, output_name):
    channels = {c for p in prompts for c in p.channels}
    overview = overview_field(field,1024)
    if overview:
        overview_planes = read_window(overview,channels,time_index,settings.projection)
    else:
        overview_planes,_ = sampled_overview(field,channels,time_index,settings.projection)
    shape = field.cyx_shape[1:]
    tile_count = sum(1 for _ in windows(shape,settings.tile_size,settings.tile_overlap))
    for slot,prompt in enumerate(prompts,1):
        started = time.perf_counter()
        prefix = f'field{index+1:04d}_t{time_index:04d}_{prompt.name}'
        options = source_field.render_options(settings.normalization,prompt.channels)
        rgb,limits = render_rgb(overview_planes,prompt.channels,settings.normalization,**options)
        # Fixed limits across all tiles prevent tile-dependent contrast changes.
        if settings.normalization == 'percentile':
            options = {'windows':{v['channel']:{'start':v['low'],'end':max(v['high'],v['low']+1e-12)} for v in limits}}
            normalization = 'metadata'
        else:
            normalization = settings.normalization
        preview_dir = output/'wevisone_previews'
        rgb.save(preview_dir/(prefix+'_input.png'))
        work = output/('.tiles_'+prefix)
        work.mkdir()
        trace = preview_dir/(prefix+'_tiles.jsonl')
        entry = {'field':field.path,'time_index':time_index,'slot':slot,'name':prompt.name,'query':prompt.text,
                 'channels':list(prompt.channels),'processing_mode':'tiled','tile_size':settings.tile_size,
                 'tile_overlap':settings.tile_overlap,'tile_count':tile_count,'tile_trace':trace.relative_to(output).as_posix(),
                 'native_size_yx':list(shape),'normalization_limits':limits,
                 'normalization_basis':'existing overview or bounded native sampling' if settings.normalization=='percentile' else settings.normalization,
                 'model_max_side':settings.max_side,'label_mode':settings.label_mode,'threshold':settings.threshold,
                 'projection':settings.projection if source_field.z_planes>1 else 'none','source_z_planes':source_field.z_planes,
                 'overlap_policy':'reciprocal unambiguous overlap IoU; farthest-from-tile-edge context owns pixels; earlier tile wins ties',
                 'match_threshold':settings.tile_match_threshold,'minimum_shared_pixels':8,
                 'measurement_notes':'Streamed moments/intensities. Exposed pixel-edge perimeter; solidity unavailable.',
                 'model':settings.model,'model_revision':predictor.manifest.get('revision'),'status':'running'}
        report['fields'].append(entry)
        write_json(output/'wevisone-run.json',report)
        stitch = DiskStitcher(work,shape,settings.tile_match_threshold,settings.label_mode=='semantic')
        skipped = predicted = high_coverage = 0
        try:
            with trace.open('w',encoding='utf-8') as stream:
                for number,window in enumerate(windows(shape,settings.tile_size,settings.tile_overlap),1):
                    tick = time.perf_counter()
                    tile = {'tile':number,'window_yxyx':list(window),'status':'running'}
                    entry['active_tile'] = tile
                    write_json(output/'wevisone-run.json',report)
                    planes = read_window(field,prompt.channels,time_index,settings.projection,window)
                    view,tile_limits = render_rgb(planes,prompt.channels,normalization,**options)
                    pixels = np.asarray(view)
                    blank = np.all(pixels>=220,axis=-1) | np.all(pixels<=15,axis=-1)
                    if settings.skip_blank_tiles and np.count_nonzero(~blank)/blank.size <= .001:
                        skipped += 1
                        local = np.zeros(pixels.shape[:2],np.uint32)
                        tile.update(status='skipped',reason='At most 0.1% pixels outside near-white (all >=220) or near-black (all <=15)')
                    else:
                        view.thumbnail((settings.max_side,settings.max_side),Image.Resampling.LANCZOS)
                        prediction = predictor.predict(view,prompt.text)
                        local,count = combine_masks(prediction.masks,pixels.shape[:2],settings.threshold,0,'instances')
                        predicted += len(prediction.masks)
                        tile.update(status='complete',model_input_size_xy=list(view.size),response=prediction.response,
                                    generated_prompt=prediction.prompt,boxes_normalized_xyxy=prediction.boxes,
                                    predicted_instances=len(prediction.masks),retained_tile_instances=count)
                        if getattr(predictor,'last_gpu_memory',None):
                            tile['gpu_memory'] = predictor.last_gpu_memory
                    tile['foreground_fraction'] = float(np.count_nonzero(local)/local.size)
                    if tile['foreground_fraction'] > .8:
                        high_coverage += 1
                        tile['review_note'] = 'Prediction covers over 80% of this tile; inspect for foreground/background or target confusion'
                    stitch.add(window,local)
                    tile['seconds'] = time.perf_counter()-tick
                    stream.write(json.dumps(tile,ensure_ascii=False)+'\n'); stream.flush()
                    print(f'  {prompt.name}: tile {number}/{tile_count}, {tile["status"]}, {tile["seconds"]:.1f}s',flush=True)
                    del planes,view,pixels,local
                    if 'prediction' in locals():
                        del prediction
            group = label_group(output,field,prompt,time_index)
            count,foreground = stitch.finish(group['0'],time_index,settings.min_area)
            entry.update(retained_instances=count,foreground_pixels=foreground,foreground_fraction=foreground/(shape[0]*shape[1]),
                         predicted_tile_instances=predicted,skipped_tiles=skipped,stitched_matches=stitch.matches,
                         ambiguous_matches=stitch.ambiguous,high_coverage_tiles=high_coverage)
            for level in range(1,len(group.attrs['multiscales'][0]['datasets'])):
                build_pyramid_level(group[str(level-1)],group[str(level)],time_index,labels=True)
            entry['measurement_rows'] = add_streamed(measurements,group['0'],field,prompt,source_field,time_index,
                                                     settings,output_name,work/'measurements.sqlite')
            # A bounded label overview, independent of the source pyramid's rounding convention.
            level = len(group.attrs['multiscales'][0]['datasets'])-1
            while level and max(group[str(level-1)].shape[-2:]) <= 1024:
                level -= 1
            small = np.asarray(group[str(level)][time_index,0,0])
            mask = np.asarray(Image.fromarray(small.astype(np.int32)).resize(rgb.size,Image.Resampling.NEAREST)) != 0
            overlay = np.asarray(rgb).copy()
            overlay[mask] = (.55*overlay[mask]+.45*np.array([255,70,180])).astype(np.uint8)
            Image.fromarray(overlay).save(preview_dir/(prefix+'_overlay.png'))
            entry.update(status='complete',seconds=time.perf_counter()-started)
            entry.pop('active_tile',None)
            history = list(group.attrs.get('ciseg_wevisonevl',{}).get('timepoints',[]))
            history.append(entry)
            group.attrs['ciseg_wevisonevl'] = {'timepoints':history}
            write_json(output/'wevisone-run.json',report)
        finally:
            stitch.close()
        # Keep scratch databases on failure for inspection; successful results need only labels and traces.
        if work.is_symlink() or work.resolve().parent != Path(output).resolve() or not work.name.startswith('.tiles_'):
            raise ValueError('Scratch cleanup target is outside the result store')
        shutil.rmtree(work)
        print(f'  {prompt.name}: {count} complete labels; {stitch.matches} seam matches, {stitch.ambiguous} ambiguous matches',flush=True)
