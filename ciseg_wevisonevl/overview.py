"""Whole-field inference on a bounded pyramid overview; native labels are streamed."""
from copy import deepcopy
import time
import numpy as np
from PIL import Image
from scipy import ndimage as ndi, sparse
import zarr
from .io import Field, write_json
from .inference import render_rgb, combine_masks
from .streaming import blocks, read_window, build_pyramid_level
from .label_output import label_group
from .resolution import choose_resolution,next_smaller_side


def select_level(field, max_side):
    """Choose the smallest compatible level still at/above the requested side."""
    root = zarr.open_group(str(field.store), mode='r')
    group = root[field.path] if field.path else root
    native = dict(zip(field.names, field.shape))
    candidates = []
    for dataset in field.multiscale['datasets']:
        array = group[dataset['path']]
        sizes = dict(zip(field.names, array.shape))
        if any(sizes[a] != native[a] for a in field.names if a not in 'xy'):
            continue
        if sizes['y'] > native['y'] or sizes['x'] > native['x']:
            continue
        candidates.append((max(sizes['y'], sizes['x']), dataset, array.shape))
    above = [c for c in candidates if c[0] >= max_side]
    # Small images are never enlarged. If all overviews are smaller, use native.
    _, dataset, shape = min(above, key=lambda c: c[0]) if above else max(candidates, key=lambda c: c[0])
    ms = deepcopy(field.multiscale)
    ms['datasets'] = [deepcopy(dataset)]
    return Field(field.store, field.path, dataset['path'], field.axes, shape, ms)


def area_weights(source, target):
    """Sparse exact pixel-footprint overlap weights, including fractional edges."""
    scale = source / target
    starts = np.arange(source, dtype=np.float64)
    rows = np.floor(starts / scale).astype(np.int64).clip(0, target-1)
    ends = (rows+1)*scale
    first = np.minimum(starts+1, ends)-starts
    second = 1-first
    columns = np.arange(source)
    split = (second > 1e-10) & (rows+1 < target)
    return sparse.csr_matrix((np.r_[first/scale, second[split]/scale],
                              (np.r_[rows, rows[split]+1], np.r_[columns, columns[split]])),
                             shape=(target, source))


def read_overview(field, max_side, time_index=0, projection='Max'):
    """Area-resample unscaled channel intensities with bounded source reads."""
    level = select_level(field, max_side)
    height, width = level.cyx_shape[1:]
    ratio = min(1., max_side/max(height, width))
    shape = (max(1, round(height*ratio)), max(1, round(width*ratio)))
    channels = range(1, field.cyx_shape[0]+1)
    if shape == (height, width):
        return read_window(level, channels, time_index, projection), level
    wy, wx = area_weights(height, shape[0]), area_weights(width, shape[1])
    planes = {c-1: np.zeros(shape, np.float64) for c in channels}
    for y, x, y1, x1 in blocks((height, width)):
        ay, ax = wy[:, y:y1], wx[:, x:x1]
        yi, xi = ay.nonzero()[0], ax.nonzero()[0]
        ya, yb, xa, xb = yi.min(), yi.max()+1, xi.min(), xi.max()+1
        ay, ax = ay[ya:yb], ax[xa:xb]
        for c, part in read_window(level, channels, time_index, projection, (y,x,y1,x1)).items():
            planes[c][ya:yb, xa:xb] += ax.dot(ay.dot(part).T).T
    return {c: p.astype(np.float32) for c,p in planes.items()}, level


def smooth_label_block(labels, native_shape, window):
    """Interpolate per-object signed distances, never interpolate integer IDs."""
    y,x,y1,x1 = window
    sy,sx = np.array(native_shape)/labels.shape
    if sy == sx == 1:
        return labels[y:y1,x:x1]
    cy = (np.arange(y,y1)+.5)/sy-.5
    cx = (np.arange(x,x1)+.5)/sx-.5
    ya,xa = max(0,int(np.floor(cy[0]))-3), max(0,int(np.floor(cx[0]))-3)
    yb,xb = min(labels.shape[0],int(np.ceil(cy[-1]))+4), min(labels.shape[1],int(np.ceil(cx[-1]))+4)
    patch = labels[ya:yb,xa:xb]
    coords = np.broadcast_arrays((cy-ya+1)[:,None], (cx-xa+1)[None,:])
    result = np.zeros((y1-y,x1-x),np.uint32)
    best = np.zeros(result.shape,np.float32)
    for label in np.unique(patch):
        if not label:
            continue
        binary = np.pad(patch == label,1)
        distance = ndi.distance_transform_edt(binary)-ndi.distance_transform_edt(~binary)
        sampled = ndi.map_coordinates(distance, coords, order=1, mode='nearest', prefilter=False)
        owns = sampled > best
        result[owns] = label
        best[owns] = sampled[owns]
    return result


def write_native_labels(output, field, prompt, labels, entry, time_index):
    group = label_group(output,field,prompt,time_index)
    for window in blocks(field.cyx_shape[1:]):
        y,x,y1,x1 = window
        group['0'][time_index,0,0,y:y1,x:x1] = smooth_label_block(labels,field.cyx_shape[1:],window)
    for level in range(1,len(group.attrs['multiscales'][0]['datasets'])):
        build_pyramid_level(group[str(level-1)],group[str(level)],time_index,labels=True)
    history = list(group.attrs.get('ciseg_wevisonevl',[]))
    history.append({**entry,'status':'complete'})
    group.attrs['ciseg_wevisonevl'] = history


def segment_frame(predictor,settings,prompts,source_field,field,output,index,time_index,report,measurements,output_name):
    side,resolution_plan = choose_resolution(predictor,settings,field.cyx_shape[1:])
    planes,level = read_overview(field,side,time_index,settings.projection)
    shape = next(iter(planes.values())).shape
    native_shape = field.cyx_shape[1:]
    scale = np.array(native_shape)/shape
    print(f'  Whole-field overview: level {level.dataset}, {level.cyx_shape[2]}x{level.cyx_shape[1]} -> {shape[1]}x{shape[0]}',flush=True)
    for slot,prompt in enumerate(prompts,1):
        tick = time.perf_counter()
        rgb,limits = render_rgb(planes,prompt.channels,settings.normalization,
                                **source_field.render_options(settings.normalization,prompt.channels))
        entry = {'field':field.path,'time_index':time_index,'slot':slot,'name':prompt.name,'query':prompt.text,
                 'channels':list(prompt.channels),'processing_mode':'pyramid_overview','status':'predicting',
                 'pyramid_dataset':level.dataset,'pyramid_size_yx':list(level.cyx_shape[1:]),
                 'model_input_size_xy':list(rgb.size),'measurement_size_yx':list(shape),'native_size_yx':list(native_shape),
                 'measurement_scale_yx':scale.tolist(),'measurement_method':'overview_scaled',
                 'measurement_notes':'Shapes measured on overview, transformed to native pixels and physical units. Intensity totals and valid counts multiplied by Y*X scale; min/max/mean unchanged. Estimates may differ from the interpolated native raster.',
                 'label_interpolation':'bilinear per-instance signed distance; positive maximum owns; lower ID wins ties',
                 'normalization_limits':limits,'projection':settings.projection if source_field.z_planes>1 else 'none',
                 'source_z_planes':source_field.z_planes,'label_mode':settings.label_mode,'threshold':settings.threshold,
                 'model':settings.model,'model_revision':predictor.manifest.get('revision')}
        report['fields'].append(entry)
        write_json(output/'wevisone-run.json',report)
        attempts=[]
        while True:
            # A retry changes the overview before labels or measurements are written.
            try:
                prediction = predictor.predict(rgb,prompt.text)
            except Exception as error:
                import torch
                if not isinstance(error,torch.cuda.OutOfMemoryError) or side<=128:
                    raise
                attempts.append({'side_limit':side,'size_xy':list(rgb.size),'status':'cuda_out_of_memory'})
                entry['resolution_attempts']=attempts.copy()
                write_json(output/'wevisone-run.json',report)
            else:
                break
            # Leave the exception block first so its traceback releases tensors.
            import gc
            gc.collect()
            if getattr(predictor,'cuda_device',None):
                with torch.cuda.device(predictor.cuda_device):
                    torch.cuda.empty_cache()
            side=next_smaller_side(side)
            print(f'  GPU memory fallback: retry complete field at side {side}',flush=True)
            planes,level=read_overview(field,side,time_index,settings.projection)
            shape=next(iter(planes.values())).shape
            scale=np.array(native_shape)/shape
            rgb,limits=render_rgb(planes,prompt.channels,settings.normalization,
                                  **source_field.render_options(settings.normalization,prompt.channels))
        entry.update(pyramid_dataset=level.dataset,pyramid_size_yx=list(level.cyx_shape[1:]),
                     model_input_size_xy=list(rgb.size),measurement_size_yx=list(shape),
                     measurement_scale_yx=scale.tolist(),normalization_limits=limits,
                     resolution_plan=resolution_plan,resolution_attempts=attempts,
                     actual_side_limit=side)
        labels,count = combine_masks(prediction.masks,shape,settings.threshold,settings.min_area/np.prod(scale),settings.label_mode)
        entry.update({'response':prediction.response,'generated_prompt':prediction.prompt,
                      'boxes_normalized_xyxy':prediction.boxes,'predicted_instances':len(prediction.masks),
                      'retained_instances':count,'overview_foreground_pixels':int(np.count_nonzero(labels)),
                      'foreground_fraction':float(np.count_nonzero(labels)/labels.size),
                      'gpu_memory':getattr(predictor,'last_gpu_memory',None),'prediction_seconds':time.perf_counter()-tick})
        entry['measurement_rows'] = measurements.add(labels,field,prompt,source_field,time_index,settings,output_name,planes,scale_yx=scale)
        prefix = f'field{index+1:04d}_t{time_index:04d}_{prompt.name}'
        rgb.save(output/'wevisone_previews'/(prefix+'_input.png'))
        np.save(output/'wevisone_previews'/(prefix+'_overview_labels.npy'),labels,allow_pickle=False)
        overlay = np.asarray(rgb).copy()
        foreground = labels > 0
        overlay[foreground] = (.55*overlay[foreground]+.45*np.array([255,70,180])).astype(np.uint8)
        Image.fromarray(overlay).save(output/'wevisone_previews'/(prefix+'_overlay.png'))
        entry['status'] = 'writing_native_labels'
        write_json(output/'wevisone-run.json',report)
        write_native_labels(output,field,prompt,labels,entry,time_index)
        entry.update(status='complete',seconds=time.perf_counter()-tick)
        print(f'  {prompt.name}: {count} instances; {entry["seconds"]:.1f}s including native labels',flush=True)
        write_json(output/'wevisone-run.json',report)
