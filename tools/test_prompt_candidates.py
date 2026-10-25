"""Run reproducible, exploratory prompt comparisons without modifying model outputs."""
import argparse,json,sys,time
from dataclasses import replace
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT,Settings
from ciseg_wevisonevl.inference import Predictor,render_rgb,combine_masks
from ciseg_wevisonevl.io import inspect_store,write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--cases',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    cases=json.loads(args.cases.read_text());summary_path=args.output/'summary.json'
    results=json.loads(summary_path.read_text()) if summary_path.exists() else {}
    settings=Settings(device='cuda:0',max_new_tokens=4096)
    predictor=Predictor(settings)
    for i,case in enumerate(cases,1):
        if case['id'] in results:continue
        print(f"PROMPT {i}/{len(cases)} {case['id']}: {case['text']}",flush=True)
        field=inspect_store(ROOT/'publicdata/ome-zarr'/(case['sample']+'.ome.zarr'),[])[0]
        channels=tuple(map(int,case['channels'].split(',')))
        rgb,limits=render_rgb(field.pixels(channels),channels,case.get('normalization','percentile'))
        native_shape=(rgb.height,rgb.width);rgb.thumbnail((1024,1024),Image.Resampling.LANCZOS)
        record={**case,'normalization_limits':limits,'input_size_xy':list(rgb.size)};tick=time.perf_counter()
        rgb.save(args.output/(case['id']+'-input.png'))
        try:
            prediction=predictor.predict(rgb,case['text']);labels,count=combine_masks(prediction.masks,native_shape)
            np.savez_compressed(args.output/(case['id']+'-labels.npz'),labels=labels)
            preview=np.asarray(Image.fromarray(labels.astype(np.int32)).resize(rgb.size,Image.Resampling.NEAREST))>0
            overlay=np.asarray(rgb).copy();overlay[preview]=(.55*overlay[preview]+.45*np.array([255,50,160])).astype(np.uint8)
            Image.fromarray(overlay).save(args.output/(case['id']+'-overlay.png'))
            record.update(status='complete',objects=count,coverage=float(np.count_nonzero(labels)/labels.size),response=prediction.response)
            reference=ROOT/'publicdata/ome-zarr'/(case['sample']+'_reference.npy')
            if reference.exists():
                truth=np.load(reference,allow_pickle=False)>0;mask=labels>0;intersection=int((truth&mask).sum())
                record['foreground_iou']=intersection/int((truth|mask).sum()) if (truth|mask).any() else 1
                record['foreground_dice']=2*intersection/(int(truth.sum())+int(mask.sum())) if truth.any() or mask.any() else 1
        except Exception as exc:record.update(status='failed',error=str(exc))
        record['seconds']=time.perf_counter()-tick;results[case['id']]=record;write_json(summary_path,results)
        print(json.dumps({k:record[k] for k in ['id','status','objects','coverage','foreground_dice','seconds'] if k in record}),flush=True)
    for sample in sorted({c['sample'] for c in cases}):
        selected=[c for c in cases if c['sample']==sample];fig,axes=plt.subplots(len(selected),2,figsize=(9,3.5*len(selected)),squeeze=False,layout='constrained')
        for row,case in enumerate(selected):
            axes[row,0].imshow(Image.open(args.output/(case['id']+'-input.png')));record=results[case['id']]
            overlay=args.output/(case['id']+'-overlay.png')
            if overlay.exists():axes[row,1].imshow(Image.open(overlay))
            axes[row,0].set_title(case['text'],fontsize=10)
            axes[row,1].set_title(f"{record['status']} | objects={record.get('objects','-')} | coverage={record.get('coverage',0):.3f}",fontsize=10)
            for axis in axes[row]:axis.axis('off')
        fig.savefig(args.output/(sample+'-comparison.jpg'),dpi=100);plt.close(fig)


if __name__=='__main__':main()
