from dataclasses import replace
from types import SimpleNamespace
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
import numpy as np
import pytest
import zarr
from ciseg_wevisonevl.engine import run,preflight
from ciseg_wevisonevl.settings import Settings,Prompt
from bilayers_cli import load_config


def hashes(path):
    return {str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob("*") if p.is_file()}


def volume(path, axes="tczyx", z_planes=3, height=17, width=19):
    # Distinct Z and T values make an accidental time projection detectable.
    canonical=np.zeros((2,2,z_planes,height,width),np.uint16)
    for t in range(2):
        for c in range(2):
            for z in range(z_planes):
                canonical[t,c,z]=10*t+3*c+z
                canonical[t,c,z,2+t:5+t,3+z:6+z]+=100*(z+1)
    data=np.transpose(canonical,["tczyx".index(a) for a in axes])
    root=zarr.open_group(str(path),mode="w")
    root.create_dataset("0",data=data,chunks=tuple(1 if a in "tcz" else 128 for a in axes))
    scales={"t":5,"c":1,"z":2,"y":.4,"x":.6}
    offsets={"t":7,"c":0,"z":10,"y":11,"x":12}
    kinds={"t":"time","c":"channel","z":"space","y":"space","x":"space"}
    axis_meta=[{"name":a,"type":kinds[a],**({"unit":"second"} if a=="t" else {"unit":"micrometer"} if a in "zyx" else {})} for a in axes]
    root.attrs["multiscales"]=[{"version":"0.4","axes":axis_meta,"datasets":[{"path":"0","coordinateTransformations":[{"type":"scale","scale":[scales[a] for a in axes]},{"type":"translation","translation":[offsets[a] for a in axes]}]}]}]
    root.attrs["omero"]={"channels":[{"label":"A"},{"label":"B"}]}
    (path/"OME").mkdir()
    (path/"OME/METADATA.ome.xml").write_text(f'<OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06"><Image ID="Image:0"><Pixels ID="Pixels:0" Type="uint16" SizeT="2" SizeC="2" SizeZ="{z_planes}" SizeY="{height}" SizeX="{width}" PhysicalSizeZ="2"><Channel ID="Channel:0:0"/><Channel ID="Channel:0:1"/></Pixels></Image></OME>')
    # Original 3D labels must never be averaged or max-projected as instance IDs.
    if z_planes>1:
        root.create_dataset("labels/reference/0",data=np.zeros((2,z_planes,height,width),np.uint32))
        root["labels"].attrs["labels"]=["reference"]
    return canonical


class Capture:
    manifest={"repo_id":"test-only","revision":"test"}
    def __init__(self,settings):
        self.inputs=[]
    def predict(self,image,text):
        array=np.asarray(image)
        self.inputs.append(array)
        mask=np.zeros(array.shape[:2],np.float32)
        mask[2:4,3:6]=.9
        return SimpleNamespace(response="test",prompt=text,boxes=[],masks=[mask])


@pytest.mark.parametrize("method",["Max","Mean"])
@pytest.mark.parametrize("axes",["tczyx","tzcyx","tczxy"])
def test_projection_keeps_time_channels_xy_and_source_exact(tmp_path,method,axes):
    source=tmp_path/"volume.ome.zarr"
    original=volume(source,axes)
    before=hashes(source)
    predictor=Capture(None)
    output=run(source,tmp_path/"out",Settings(projection=method),[Prompt("objects","objects")],predictor_factory=lambda s:predictor)[0]
    assert hashes(source)==before
    root=zarr.open_group(str(output),mode="r")
    names=[a["name"] for a in root.attrs["multiscales"][0]["axes"]]
    expected=original.max(axis=2) if method=="Max" else original.mean(axis=2).astype(np.float32)
    np.testing.assert_array_equal(root["0"][:],expected[:,:,None])
    assert root["0"].dtype==(np.uint16 if method=="Max" else np.float32)
    assert len(predictor.inputs)==2
    labels=root["labels/wevisone_objects/0"]
    assert labels.shape==(2,1,1,17,19)
    assert "labels/reference" not in root
    ms=root.attrs["multiscales"][0]
    assert names==list("tczyx")
    assert "unit" not in next(a for a in ms["axes"] if a["name"]=="z")
    assert ms["datasets"][0]["coordinateTransformations"][0]["scale"]==[5,1,1,.4,.6]
    assert ms["datasets"][0]["coordinateTransformations"][1]["translation"]==[7,0,0,11,12]
    pixels=ET.parse(output/"OME/METADATA.ome.xml").getroot().find('.//{*}Pixels')
    assert pixels.get("SizeZ")=="1" and pixels.get("SizeT")=="2"
    assert pixels.get("Type") == ("uint16" if method=="Max" else "float")
    assert "PhysicalSizeZ" not in pixels.attrib
    report=json.loads((output/"wevisone-run.json").read_text())
    assert [f["time_index"] for f in report["fields"]]==[0,1]
    assert report["input_fields"][0]["projection"]==method


def test_2d_timeseries_is_not_projected_and_processes_every_frame(tmp_path):
    source=tmp_path/"time.ome.zarr"
    original=volume(source,z_planes=1)
    before=hashes(source)
    output=run(source,tmp_path/"out",Settings(projection="Mean"),[Prompt("cells","cell")],predictor_factory=Capture)[0]
    assert hashes(source)==before
    root=zarr.open_group(str(output),mode="r")
    np.testing.assert_array_equal(root["0"][:],original)
    assert root["0"].dtype==np.uint16
    assert root["labels/wevisone_cells/0"].shape==(2,1,1,17,19)
    assert root["labels/wevisone_cells/0"][1,0].max()==1


@pytest.mark.parametrize("method",["Max","Mean"])
def test_screen_projects_all_fields_and_all_timepoints(tmp_path,method):
    source=tmp_path/"field.ome.zarr"
    original=volume(source)
    plate=tmp_path/"screen.ome.zarr"
    root=zarr.open_group(str(plate),mode="w")
    root.attrs["plate"]={"version":"0.4","name":"screen","rows":[{"name":"A"}],"columns":[{"name":"1"}],"wells":[{"path":"A/1","rowIndex":0,"columnIndex":0}]}
    well=root.require_group("A/1")
    well.attrs["well"]={"version":"0.4","images":[{"path":"0"},{"path":"1"}]}
    for path in ["0","1"]:
        shutil.copytree(source,plate/"A/1"/path)
    before=hashes(plate)
    predictor=Capture(None)
    output=run(plate,tmp_path/"out",Settings(projection=method),[Prompt("cells","cell")],predictor_factory=lambda s:predictor)[0]
    assert hashes(plate)==before
    assert len(predictor.inputs)==4
    result=zarr.open_group(str(output),mode="r")
    assert result.attrs["plate"]==root.attrs["plate"]
    for path in ["0","1"]:
        assert result[f"A/1/{path}/0"].shape==(2,2,1,17,19)
        assert result[f"A/1/{path}/labels/wevisone_cells/0"].shape==(2,1,1,17,19)


def test_projection_option_is_advanced_default_max():
    from pathlib import Path
    config=load_config(Path(__file__).parents[1]/"config.yaml")
    option=next(p for p in config["parameters"] if p["name"]=="projection")
    assert option["default"]==Settings().projection=="Max"
    assert option["mode"]=="advanced" and option["section_id"]=="advanced"
    assert [o["value"] for o in option["options"]]==["Max","Mean"]


@pytest.mark.parametrize("method",["Max","Mean"])
def test_projected_pyramids_and_time_labels_cover_odd_edges(tmp_path,method):
    from ciseg_wevisonevl.projection import area_downsample
    source=tmp_path/"odd.ome.zarr"
    raw=volume(source,height=301,width=513)
    output=run(source,tmp_path/"out",Settings(projection=method),[Prompt("objects","objects")],predictor_factory=Capture)[0]
    root=zarr.open_group(str(output),mode="r")
    expected=raw.max(axis=2) if method=="Max" else raw.mean(axis=2).astype(np.float32)
    assert root["1"].shape==(2,2,1,151,257)
    assert root["2"].shape==(2,2,1,76,129)
    for t in range(2):
        for c in range(2):
            down1=area_downsample(expected[t,c])
            np.testing.assert_array_equal(root["1"][t,c,0],down1)
            np.testing.assert_array_equal(root["2"][t,c,0],area_downsample(down1))
        labels=root["labels/wevisone_objects"]
        np.testing.assert_array_equal(labels["1"][t,0,0],labels["0"][t,0,0,::2,::2])
        np.testing.assert_array_equal(labels["2"][t,0,0],labels["0"][t,0,0,::4,::4])
