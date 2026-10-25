"""Targeted 4B GPU checks for structured absence, token truncation and HCS."""
from dataclasses import replace
from pathlib import Path
import hashlib
import sys
import numpy as np
import zarr

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT,Settings,Prompt
from ciseg_wevisonevl.inference import Predictor,render_rgb
from ciseg_wevisonevl.engine import run
from ciseg_wevisonevl.io import write_json,inspect_store


if __name__=="__main__":
    settings=Settings(device="cuda:0")
    predictor=Predictor(settings)
    source=ROOT/"publicdata/ome-zarr/human_mitosis.ome.zarr"
    field=inspect_store(source,[Prompt("nuclei","nuclei")])[0]
    rgb,_=render_rgb(field.pixels([1]),(1,),"percentile")
    absent=predictor.predict(rgb,"elephant")
    assert not absent.masks
    checks={"structured_absence":{"passed":True,"response":absent.response}}
    predictor.settings=replace(settings,max_new_tokens=32)
    try:
        predictor.predict(rgb,"each bright fluorescent cell nucleus")
    except RuntimeError as exc:
        assert "token limit" in str(exc),str(exc)
        checks["truncation_guard"]={"passed":True,"error":str(exc)}
    else:
        raise AssertionError("Expected token-limit refusal was not exercised")
    predictor.settings=settings
    source=ROOT/"publicdata/hcs-smoke/cells.ome.zarr"
    before={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob("*") if p.is_file()}
    output=run(source,ROOT/"test-results/hcs-smoke-4B",settings,[Prompt("cell","cell")],predictor_factory=lambda s:predictor)[0]
    assert before=={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob("*") if p.is_file()}
    root=zarr.open_group(str(output),mode="r")
    for path in ["A/1/0","A/2/0"]:
        assert int(root[f"{path}/labels/wevisone_cell/0"][:].max())==1
    checks["hcs"]={"passed":True,"fields":2,"source_unchanged":True,"output":str(output)}
    write_json(ROOT/"test-results/runtime-checks-4B.json",checks)
    print(checks,flush=True)
