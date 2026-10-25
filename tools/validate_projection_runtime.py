"""4B runtime check on an explicitly derived T=2/Z=3/two-field HCS fixture."""
from dataclasses import replace
import argparse
import hashlib
from pathlib import Path
import sys
import numpy as np
import zarr

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT,Settings,Prompt
from ciseg_wevisonevl.engine import run
from ciseg_wevisonevl.inference import Predictor
from ciseg_wevisonevl.io import write_json


def digest(path):
    return {str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob("*") if p.is_file()}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"test-results/projection-runtime-canonical")
    args=parser.parse_args()
    source=ROOT/"publicdata/projection-smoke/time-volume-screen.ome.zarr"
    cell=zarr.open_group(str(ROOT/"publicdata/ome-zarr/cell.ome.zarr"),mode="r")["0"][0,0,0]
    volume=np.stack([np.stack([np.zeros_like(cell),cell,cell]),
                     np.stack([np.zeros_like(cell),np.roll(cell,25,axis=1),np.roll(cell,25,axis=1)])])[:,None]
    if not source.exists():
        root=zarr.open_group(str(source),mode="w")
        root.attrs["plate"]={"version":"0.4","name":"Derived projection/time/HCS fixture; not biological 3D data",
                             "rows":[{"name":"A"}],"columns":[{"name":"1"}],"wells":[{"path":"A/1","rowIndex":0,"columnIndex":0}]}
        well=root.require_group("A/1")
        well.attrs["well"]={"version":"0.4","images":[{"path":"0"},{"path":"1"}]}
        for field in ["0","1"]:
            image=well.create_group(field)
            image.create_dataset("0",data=volume,chunks=(1,1,1,256,256))
            image.attrs["multiscales"]=[{"version":"0.4","axes":[{"name":"t","type":"time","unit":"second"},{"name":"c","type":"channel"},{"name":"z","type":"space"},{"name":"y","type":"space","unit":"micrometer"},{"name":"x","type":"space","unit":"micrometer"}],
                                         "datasets":[{"path":"0","coordinateTransformations":[{"type":"scale","scale":[5,1,1,.107,.107]}]}]}]
    before=digest(source)
    settings=Settings(device="cuda:0")
    predictor=Predictor(settings)
    checks=[]
    for method in ["Max","Mean"]:
        out=run(source,args.output/method,replace(settings,projection=method),[Prompt("cell","cell")],predictor_factory=lambda s:predictor)[0]
        root=zarr.open_group(str(out),mode="r")
        expected=volume.max(axis=2) if method=="Max" else volume.mean(axis=2).astype(np.float32)
        for field in ["0","1"]:
            image=root[f"A/1/{field}"]
            np.testing.assert_array_equal(image["0"][:],expected[:,:,None])
            labels=image["labels/wevisone_cell/0"][:,0,0]
            assert labels.shape==(2,*cell.shape)
            assert all(frame.max()==1 for frame in labels)
            centers=[float(np.where(frame>0)[1].mean()) for frame in labels]
            assert 15<centers[1]-centers[0]<35,centers
        assert before==digest(source)
        checks.append({"method":method,"passed":True,"fields":2,"timepoints_per_field":2,"source_z_planes":3,
                       "projection_pixels_exact":True,"source_unchanged":True,"label_motion_checked":True,"output":str(out)})
        write_json(args.output/"checks.json",checks)
    print(checks,flush=True)
