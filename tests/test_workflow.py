from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import numpy as np
import pytest
import zarr

from ciseg_wevisonevl.settings import Settings, Prompt
from ciseg_wevisonevl.inference import combine_masks, render_rgb, is_absent_response
from ciseg_wevisonevl.engine import run, preflight
from tools.prepare_publicdata import write_store
from bilayers_cli import load_config, validate_config, generate_cli_command
from wrapper import build_parser, settings_from_args
import shlex


def digest(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob("*") if p.is_file()}


@pytest.fixture
def source(tmp_path):
    source = tmp_path/"in"/"test.ome.zarr"
    source.parent.mkdir()
    data = np.arange(24*32*3,dtype=np.uint16).reshape(24,32,3)
    write_store(source,data,"sample",pixel_um=.34)
    return source


class FakePredictor:
    manifest = {"repo_id":"unit-test-only", "revision":"test"}
    def __init__(self, settings):
        pass
    def predict(self, image, text):
        mask = np.zeros((image.height,image.width), np.float32)
        if text != "absent":
            mask[2:10,4:15]=.9
        return SimpleNamespace(masks=[] if text=="absent" else [mask], response="None" if text=="absent" else "<box><0><0><1000><1000><OBJ></box>",prompt=text,boxes=[])


def test_four_independent_groups_native_coordinates_and_source_untouched(source,tmp_path):
    before=digest(source)
    prompts=[Prompt(f"slot{i}","objects" if i<4 else "absent",(1,2,3)) for i in range(1,5)]
    output=run(source,tmp_path/"out",Settings(),prompts,predictor_factory=FakePredictor)[0]
    assert digest(source)==before
    original=zarr.open_group(str(source), mode="r")
    root=zarr.open_group(str(output), mode="r")
    assert root.attrs["multiscales"]==original.attrs["multiscales"]
    np.testing.assert_array_equal(root["0"][:],original["0"][:])
    assert len(root["labels"].attrs["labels"])==4
    for i in range(1,5):
        group=root[f"labels/wevisone_slot{i}"]
        assert group["0"].shape==(1,1,1,24,32)
        assert group["0"].dtype==np.uint32
        assert group.attrs["multiscales"][0]["datasets"][0]["coordinateTransformations"][0]["scale"]==[1,1,1,.34,.34]
        assert int(group["0"][:].max())==(1 if i<4 else 0)
    report=json.loads((output/"wevisone-run.json").read_text())
    assert report["status"]=="complete" and len(report["fields"])==4


def test_bad_channel_fails_before_model_load(source,tmp_path):
    root=zarr.open_group(str(source), mode="a")
    def must_not_load(settings):
        pytest.fail("Model loaded before metadata preflight")
    with pytest.raises(ValueError,match="channel does not exist"):
        run(source,tmp_path/"out",Settings(),[Prompt("nuclei","nuclei",(99,))],predictor_factory=must_not_load)
    assert not (tmp_path/"out").exists()


def test_hcs_all_fields_preflight_and_preserved_plate(source,tmp_path):
    import shutil
    plate=tmp_path/"plate.ome.zarr"
    root=zarr.open_group(str(plate),mode="w")
    root.attrs["plate"]={"version":"0.4","rows":[{"name":"A"}],"columns":[{"name":"1"}],"wells":[{"path":"A/1","rowIndex":0,"columnIndex":0}]}
    well=root.require_group("A/1")
    well.attrs["well"]={"version":"0.4","images":[{"path":"0"},{"path":"1"}]}
    for field in ["0","1"]:
        shutil.copytree(source,plate/"A"/"1"/field)
    before=digest(plate)
    out=run(plate,tmp_path/"out",Settings(),[Prompt("nuclei","nuclei")],predictor_factory=FakePredictor)[0]
    assert digest(plate)==before
    result=zarr.open_group(str(out),mode="r")
    assert result.attrs["plate"]==root.attrs["plate"]
    for field in ["0","1"]:
        assert f"A/1/{field}/labels/wevisone_nuclei/0" in result


def test_channel_missing_in_last_hcs_field_fails_before_any_model(source,tmp_path):
    with pytest.raises(ValueError,match="channel does not exist"):
        preflight(source,tmp_path/"out",Settings(),[Prompt("nuclei","nuclei",(4,))])


def test_incomplete_run_never_published(source,tmp_path):
    class Fails(FakePredictor):
        def predict(self,*args):
            raise RuntimeError("inference failure")
    with pytest.raises(RuntimeError,match="inference failure"):
        run(source,tmp_path/"out",Settings(),[Prompt("nuclei","nuclei")],predictor_factory=Fails)
    assert not list((tmp_path/"out").glob("*.ome.zarr"))
    partial=list((tmp_path/"out").glob("*.ome.zarr.partial-*"))[0]
    assert json.loads((partial/"wevisone-run.json").read_text())["status"]=="failed"


def test_overlap_confidence_and_semantic_union():
    a=np.zeros((4,5),np.float32); a[:,1:4]=.8
    b=np.zeros_like(a); b[:,2:]=.9
    labels,count=combine_masks([a,b],a.shape)
    assert count==2
    assert np.all(labels[:,1]==1) and np.all(labels[:,2:]==2)
    binary,count=combine_masks([a,b],a.shape,mode="semantic")
    assert set(np.unique(binary))=={0,1}
    np.testing.assert_array_equal(binary>0,(a>.5)|(b>.5))


def test_uint8_rgb_is_unchanged():
    rgb=np.arange(3*4*5,dtype=np.uint8).reshape(3,4,5)
    result,limits=render_rgb(rgb,(1,2,3),"dtype")
    np.testing.assert_array_equal(np.asarray(result),rgb.transpose(1,2,0))


def test_upstream_structured_absence_is_empty_not_a_failure():
    assert is_absent_response("None")
    assert is_absent_response("<ref>elephant</ref><box>none</box>")
    assert not is_absent_response("<ref>elephant</ref><box><0><0><1000><1000><OBJ></box>")
    assert not is_absent_response("I see none but here is an invalid box")


def test_only_4b_and_no_model_selection_in_public_interfaces():
    from ciseg_wevisonevl.settings import MODELS
    assert list(MODELS)==["4B"]
    assert Settings().model=="4B"
    config=load_config(Path(__file__).parents[1]/"config.yaml")
    assert "model" not in {p["name"] for p in config["parameters"]}
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--infolder","in","--outfolder","out","--model","2B"])


def test_preserves_translation_and_pyramid_transforms(tmp_path):
    source=tmp_path/"in"/"large.ome.zarr"
    source.parent.mkdir()
    write_store(source,np.zeros((300,301),np.uint8),"large",pixel_um=.5)
    root=zarr.open_group(str(source),mode="a")
    ms=root.attrs["multiscales"]
    ms[0]["datasets"][0]["coordinateTransformations"].append({"type":"translation","translation":[0,0,0,20,30]})
    root.attrs["multiscales"]=ms
    output=run(source,tmp_path/"out",Settings(),[Prompt("cells","cells")],predictor_factory=FakePredictor)[0]
    result=zarr.open_group(str(output),mode="r")
    labelms=result["labels/wevisone_cells"].attrs["multiscales"][0]
    assert labelms["datasets"][0]["coordinateTransformations"][-1]["translation"]==[0,0,0,20,30]
    assert labelms["datasets"][1]["coordinateTransformations"][0]["scale"]==[1,1,1,2,2]


def test_bilayers_defaults_and_disabled_first_prompt():
    config=load_config(Path(__file__).parents[1]/"config.yaml")
    assert not validate_config(config)
    for spec in config["parameters"]:
        values={spec["name"]:spec.get("default")}
    command=generate_cli_command(config,{"infolder":"in","outfolder":"out","prompt_1":"","prompt_2":"cells"})
    args=build_parser().parse_args(shlex.split(command)[2:])
    settings,prompts=settings_from_args(args)
    assert len(prompts)==1 and prompts[0].text=="cells" and prompts[0].name=="target2"
    with pytest.raises(ValueError,match="one and four"):
        Settings().validate([])
    with pytest.raises(ValueError,match="one and four"):
        Settings().validate([Prompt(f"n{i}","nuclei") for i in range(5)])
    with pytest.raises(ValueError,match="unique"):
        Settings().validate([Prompt("same","cells"),Prompt("same","nuclei")])
