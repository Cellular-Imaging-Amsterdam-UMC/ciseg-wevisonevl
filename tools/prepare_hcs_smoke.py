"""Make a two-well HCS test plate from the public 2D phase cell; no new pixels."""
from pathlib import Path
import shutil
import sys
import zarr

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT


def prepare():
    source=ROOT/"publicdata/ome-zarr/cell.ome.zarr"
    plate=ROOT/"publicdata/hcs-smoke/cells.ome.zarr"
    if not source.exists():
        raise FileNotFoundError("Run tools/prepare_publicdata.py first")
    if plate.exists():
        raise FileExistsError(plate)
    root=zarr.open_group(str(plate),mode="w")
    root.attrs["plate"]={"version":"0.4","name":"Repeated public cell HCS smoke fixture",
                         "acquisitions":[{"id":0,"name":"Public 2D sample","maximumfieldcount":1}],
                         "rows":[{"name":"A"}],"columns":[{"name":"1"},{"name":"2"}],
                         "wells":[{"path":"A/1","rowIndex":0,"columnIndex":0},
                                  {"path":"A/2","rowIndex":0,"columnIndex":1}]}
    for column in ["1","2"]:
        well=root.require_group(f"A/{column}")
        well.attrs["well"]={"version":"0.4","images":[{"path":"0","acquisition":0}]}
        shutil.copytree(source,plate/"A"/column/"0")
    print(plate)


if __name__=="__main__":
    prepare()
