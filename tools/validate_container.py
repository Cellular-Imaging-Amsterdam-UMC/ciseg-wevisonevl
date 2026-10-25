"""Validate the offline model inventory and real GPU workflow inside the image."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import MODEL_REVISIONS, MODELS, Prompt, Settings


def inventory():
    folder = Path(Settings().models_root)/'WeVisOne-VL-4B'
    manifest = json.loads((folder/'download-manifest.json').read_text())
    assert manifest['repo_id'] == MODELS['4B']
    assert manifest['revision'] == MODEL_REVISIONS['4B']
    for entry in manifest['files']:
        path = folder/entry['path']
        assert path.is_file() and path.stat().st_size == entry['size'], path
    assert (folder/'LICENSE').is_file() and (folder/'mask_decoder.pt').is_file()
    return {'model_revision': manifest['revision'], 'model_bytes': sum(e['size'] for e in manifest['files']),
            'inventory_and_sizes_verified': True}


def digest(folder):
    return {p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory-only', action='store_true')
    parser.add_argument('--input-root', type=Path, default=Path('/data/in'))
    parser.add_argument('--output-root', type=Path, default=Path('/data/out'))
    parser.add_argument('--cases', default='cell,organoids_im10')
    parser.add_argument('--hcs', action='store_true', help='Also check a derived two-field/time/Z fixture')
    args = parser.parse_args(argv)
    report = inventory()
    if args.inventory_only:
        print(json.dumps(report), flush=True)
        return 0
    import resource
    import numpy as np
    import torch
    import zarr
    from ciseg_wevisonevl.engine import run
    from ciseg_wevisonevl.inference import Predictor
    assert torch.cuda.is_available(), 'CUDA must be available for release validation'
    args.output_root.mkdir(parents=True, exist_ok=True)
    settings = Settings(device='cuda:0')
    torch.cuda.reset_peak_memory_stats()
    tick = time.perf_counter()
    predictor = Predictor(settings)
    report.update(torch=torch.__version__, cuda_runtime=torch.version.cuda,
                  gpu=torch.cuda.get_device_name(0), gpu_total_gib=torch.cuda.get_device_properties(0).total_memory/2**30,
                  bf16_supported=torch.cuda.is_bf16_supported(), results=[])
    try:
        for sample in args.cases.split(','):
            source = args.input_root/(sample+'.ome.zarr')
            before = digest(source)
            name, text = ('cell','cell') if sample == 'cell' else ('organoids','organoids')
            output = run(source,args.output_root/sample,settings,[Prompt(name,text)],predictor_factory=lambda _:predictor)[0]
            original = zarr.open_group(str(source),mode='r')
            result = zarr.open_group(str(output),mode='r')
            for dataset in original.attrs['multiscales'][0]['datasets']:
                np.testing.assert_array_equal(original[dataset['path']][:],result[dataset['path']][:])
            assert before == digest(source)
            run_report = json.loads((output/'wevisone-run.json').read_text())
            row = {'sample':sample,'passed':True,'source_unchanged':True,'instances':[r['retained_instances'] for r in run_report['fields']]}
            reference = args.input_root/(sample+'_reference.npy')
            if reference.exists():
                ref = np.load(reference,allow_pickle=False)>0
                labels = result[f'labels/wevisone_{name}/0'][0,0,0]>0
                row['foreground_dice'] = 2*int((ref&labels).sum())/max(1,int(ref.sum())+int(labels.sum()))
            report['results'].append(row)
            print(json.dumps(row),flush=True)
        if args.hcs:
            cell = zarr.open_group(str(args.input_root/'cell.ome.zarr'),mode='r')['0'][0,0,0]
            volume = np.stack([np.stack([np.zeros_like(cell),cell,cell]),
                               np.stack([np.zeros_like(cell),np.roll(cell,25,axis=1),np.roll(cell,25,axis=1)])])[:,None]
            source = args.output_root/'derived-fixture.ome.zarr'
            fixture = zarr.open_group(str(source),mode='w')
            fixture.attrs['plate'] = {'wells':[{'path':'A/1'}],'name':'Derived validation fixture; not an acquired 3D volume'}
            fixture.require_group('A/1').attrs['well'] = {'images':[{'path':'0'},{'path':'1'}]}
            for field in ('0','1'):
                group = fixture.require_group('A/1/'+field)
                group.create_dataset('0',data=volume,chunks=(1,1,1,256,256))
                group.attrs['multiscales'] = [{'version':'0.4','axes':[{'name':a} for a in 'tczyx'],'datasets':[{'path':'0'}]}]
            before = digest(source)
            for projection in ('Max','Mean'):
                output = run(source,args.output_root/('hcs-'+projection),replace(settings,projection=projection),[Prompt('cell','cell')],predictor_factory=lambda _:predictor)[0]
                result = zarr.open_group(str(output),mode='r')
                expected = volume.max(axis=2) if projection == 'Max' else volume.mean(axis=2).astype(np.float32)
                for field in ('0','1'):
                    group = result['A/1/'+field]
                    np.testing.assert_array_equal(group['0'][:],expected[:,:,None])
                    labels = group['labels/wevisone_cell/0'][:,0,0]
                    assert all(frame.max()==1 for frame in labels)
                    centers = [float(np.where(frame>0)[1].mean()) for frame in labels]
                    assert 15 < centers[1]-centers[0] < 35, centers
                assert before == digest(source)
                report['results'].append({'sample':'derived-hcs','projection':projection,'passed':True,'fields':2,'timepoints':2,'source_unchanged':True})
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        report.update(peak_cuda_allocated_gib=torch.cuda.max_memory_allocated()/2**30,
                      peak_cuda_reserved_gib=torch.cuda.max_memory_reserved()/2**30,
                      peak_process_rss_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20,
                      elapsed_seconds=time.perf_counter()-tick)
        (args.output_root/'container-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report),flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
