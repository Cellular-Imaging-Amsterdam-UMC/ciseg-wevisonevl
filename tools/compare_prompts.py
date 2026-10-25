"""Compare up to four user-specified descriptions against an optional foreground reference."""
import argparse
from pathlib import Path
import sys
import numpy as np
import zarr

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT, Settings, Prompt
from ciseg_wevisonevl.engine import run
from ciseg_wevisonevl.io import write_json


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample",default="organoids_im9")
    parser.add_argument("--prompt",action="append",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    source=ROOT/"publicdata"/"ome-zarr"/(args.sample+".ome.zarr")
    prompts=[Prompt(f"description{i}",text) for i,text in enumerate(args.prompt,1)]
    outputs=run(source,args.output,Settings(device="cuda:0"),prompts)
    reference_file=source.parent/(args.sample+"_reference.npy")
    scores=[]
    if reference_file.exists():
        reference=np.load(reference_file,allow_pickle=False)>0
        root=zarr.open_group(str(outputs[0]),mode="r")
        for prompt in prompts:
            mask=np.squeeze(root[f"labels/wevisone_{prompt.name}/0"][:])>0
            intersection=int((reference&mask).sum())
            union=int((reference|mask).sum())
            scores.append({"prompt":prompt.text,"foreground_iou":intersection/union if union else 1,
                           "foreground_dice":2*intersection/(int(reference.sum())+int(mask.sum())) if reference.any() or mask.any() else 1})
        write_json(args.output/"foreground-scores.json",scores)
        print(scores,flush=True)
