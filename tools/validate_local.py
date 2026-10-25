"""Run real-model tests on retained public 2D data; report behavior and reference Dice."""
import argparse
from dataclasses import replace
import gc
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
import zarr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT, Settings, Prompt
from ciseg_wevisonevl.inference import Predictor
from ciseg_wevisonevl.engine import run
from ciseg_wevisonevl.io import write_json


def tree_digest(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob("*") if p.is_file()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"test-results"/"public-validation")
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    cases=[("cell",[Prompt("cell","cell")],"percentile"),
           ("human_mitosis",[Prompt("nuclei","cell nuclei"),Prompt("bright_nuclei","bright round cell nuclei"),
                             Prompt("mitotic","dividing cells"),Prompt("organoid_control","organoid")],"percentile"),
           ("immunohistochemistry",[Prompt("nuclei","cell nuclei",(1,2,3)),Prompt("glands","colonic glands",(1,2,3))],"dtype"),
           ("organoids_im9",[Prompt("organoids","organoids")],"percentile"),
           ("organoids_im10",[Prompt("organoids","organoids")],"percentile")]
    results=[]
    for model in ["4B"]:
        settings=Settings(device="cuda:0")
        import torch
        torch.cuda.reset_peak_memory_stats()
        predictor=Predictor(settings)
        for name,prompts,normalization in cases:
            source=ROOT/"publicdata"/"ome-zarr"/(name+".ome.zarr")
            output_dir=args.output/model/name
            before=tree_digest(source)
            tick=time.perf_counter()
            row={"model":model,"sample":name}
            try:
                existing=list(output_dir.glob("*.ome.zarr")) if output_dir.exists() else []
                output=existing[0] if existing else run(source,output_dir,replace(settings,normalization=normalization),prompts,predictor_factory=lambda s:predictor)[0]
                report=json.loads((output/"wevisone-run.json").read_text())
                original=zarr.open_group(str(source),mode="r")
                result=zarr.open_group(str(output),mode="r")
                for ds in original.attrs["multiscales"][0]["datasets"]:
                    np.testing.assert_array_equal(original[ds["path"]][:],result[ds["path"]][:])
                assert before==tree_digest(source)
                row.update(status="passed",output=str(output),source_unchanged=True,
                           labels=[{"name":f["name"],"count":f["retained_instances"],"foreground_pixels":f["foreground_pixels"],"seconds":f["seconds"]} for f in report["fields"]])
                reference=source.parent/(name+"_reference.npy")
                if reference.exists():
                    reference=np.load(reference,allow_pickle=False)>0
                    labels=result["labels/wevisone_organoids/0"][0,0]>0
                    intersection=int((reference & labels).sum())
                    union=int((reference | labels).sum())
                    row["foreground_iou"]=intersection/union if union else 1.
                    row["foreground_dice"]=2*intersection/(int(reference.sum())+int(labels.sum())) if reference.any() or labels.any() else 1.
                    row["reference_note"]="microSAM consensus masks; foreground agreement only, not instance accuracy"
            except Exception as exc:
                row.update(status="failed",error=f"{type(exc).__name__}: {exc}")
            row["wall_seconds"]=time.perf_counter()-tick
            row["peak_cuda_allocated_gib"]=torch.cuda.max_memory_allocated()/2**30
            results.append(row)
            print(json.dumps(row),flush=True)
            write_json(args.output/"summary-4B.json",results)
        del predictor
        gc.collect()
        torch.cuda.empty_cache()
    return int(any(r["status"]=="failed" for r in results))


if __name__=="__main__":
    raise SystemExit(main())
