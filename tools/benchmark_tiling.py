"""Benchmark VLM tile context and experimental seam fusion against an independent 2D reference."""
import json,sys,time
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT,Settings
from ciseg_wevisonevl.inference import Predictor,render_rgb,combine_masks
from ciseg_wevisonevl.io import inspect_store,write_json
from tools.experimental_tiling import windows,InstanceStitcher


def main():
    output=ROOT/'test-results/tiling-research';output.mkdir(parents=True,exist_ok=True)
    field=inspect_store(ROOT/'publicdata/ome-zarr/organoids_im10.ome.zarr',[])[0]
    rgb,limits=render_rgb(field.pixels([1]),(1,),'percentile')
    truth=np.load(ROOT/'publicdata/ome-zarr/organoids_im10_reference.npy',allow_pickle=False)>0
    predictor=Predictor(Settings(device='cuda:0',max_new_tokens=4096));rows=[]
    for size in [512,768,1024]:
        overlap=size//4;stitch=InstanceStitcher(truth.shape);tick=time.perf_counter();errors=[]
        tiles=windows(truth.shape,size,overlap)
        for index,(y,x,h,w) in enumerate(tiles):
            print(f'TILE BENCH {size}: {index+1}/{len(tiles)}',flush=True)
            try:
                prediction=predictor.predict(rgb.crop((x,y,x+w,y+h)),'organoids')
                labels,count=combine_masks(prediction.masks,(h,w));stitch.add(labels,y,x)
            except Exception as exc:errors.append(str(exc));break
        if errors:
            rows.append({'tile_size':size,'overlap':overlap,'status':'failed','errors':errors,'seconds':time.perf_counter()-tick})
        else:
            labels,stats=stitch.finish();mask=labels>0;intersection=int((truth&mask).sum())
            dice=2*intersection/(int(truth.sum())+int(mask.sum())) if truth.any() or mask.any() else 1
            np.savez_compressed(output/f'tiles-{size}.npz',labels=labels)
            preview=np.asarray(rgb).copy();preview[mask]=(.55*preview[mask]+.45*np.array([255,50,160])).astype(np.uint8)
            Image.fromarray(preview).save(output/f'tiles-{size}-overlay.jpg')
            rows.append({'tile_size':size,'overlap':overlap,'tiles':len(tiles),'status':'complete','foreground_dice':dice,
                         'seconds':time.perf_counter()-tick,**stats,'normalization':'One full-field percentile transform, reused for all tiles'})
        write_json(output/'benchmark.json',rows);print(json.dumps(rows[-1]),flush=True)


if __name__=='__main__':main()
