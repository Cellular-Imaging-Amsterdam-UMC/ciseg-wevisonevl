import csv
import hashlib
from pathlib import Path
import shutil
from types import SimpleNamespace

import numpy as np
import pytest
import zarr

from ciseg_wevisonevl.engine import preflight, run
from ciseg_wevisonevl.settings import Prompt, Settings
from wrapper import build_parser, settings_from_args


def digest(path):
    return {p.relative_to(path).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}


def labeled_source(path, axes='tczyx', z_planes=1):
    pixels=np.arange(2*1*z_planes*8*10,dtype=np.uint16).reshape(2,1,z_planes,8,10)
    stored=pixels if axes=='tczyx' else pixels[:,:,0]
    group=zarr.open_group(str(path),mode='w')
    group.create_dataset('0',data=stored)
    group.attrs['multiscales']=[{'version':'0.4','axes':[{'name':a} for a in axes],
                                'datasets':[{'path':'0'}]}]
    group.attrs['labels']=['reference','wevisone_target1']
    container=group.create_group('labels')
    container.attrs['labels']=['reference','wevisone_target1']
    for name, value in [('reference',11),('wevisone_target1',31)]:
        label=container.create_group(name)
        labels=np.zeros(pixels.shape,np.uint32);labels[:,:,:,1:4,2:6]=value
        label.create_dataset('0',data=labels)
        label.create_dataset('1',data=labels[...,::2,::2])
        label.attrs['multiscales']=[{'version':'0.4','axes':[{'name':a} for a in 'tczyx'],
                                    'datasets':[{'path':'0'},{'path':'1'}]}]
        label.attrs['image-label']={'version':'0.4','source':{'image':'../../'},'colors':[{'label-value':value,'rgba':[255,0,0,255]}]}
    return pixels


class Mask:
    manifest={'revision':'test-only'}
    def __init__(self,settings):pass
    def predict(self,image,text):
        mask=np.zeros((image.height,image.width),np.float32);mask[2:5,3:7]=1
        return SimpleNamespace(response='test',prompt=text,boxes=[],masks=[mask])


@pytest.mark.parametrize('policy',['keep','remove'])
@pytest.mark.parametrize('axes',['tczyx','tcyx'])
def test_existing_2d_labels_are_kept_or_removed_without_changing_inputs(tmp_path,policy,axes):
    source=tmp_path/'source.ome.zarr'
    pixels=labeled_source(source,axes)
    before=digest(source)
    old_label_files=digest(source/'labels')
    output=run(source,tmp_path/'out',Settings(input_labels=policy),[Prompt('fresh','cell')],predictor_factory=Mask)[0]
    result=zarr.open_group(str(output),mode='r')
    np.testing.assert_array_equal(result['0'][:],pixels)
    assert digest(source)==before
    assert result['labels/wevisone_fresh/0'].shape==(2,1,1,8,10)
    if policy=='keep':
        for name in ('reference','wevisone_target1'):
            for file, checksum in digest(source/'labels'/name).items():
                assert digest(output/'labels'/name)[file]==checksum
        assert result['labels'].attrs['labels']==['reference','wevisone_target1','wevisone_fresh']
        assert result.attrs['ciseg_wevisonevl_input_labels']['action']=='preserved'
    else:
        assert result['labels'].attrs['labels']==['wevisone_fresh']
        assert 'reference' not in result['labels'] and 'wevisone_target1' not in result['labels']
        assert 'labels' not in result.attrs
        assert result.attrs['ciseg_wevisonevl_input_labels']['action']=='removed_from_result'
    with (tmp_path/'out/measurements.csv').open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.DictReader(stream))
    assert len(rows)==2 and {row['prompt_name'] for row in rows}=={'fresh'}


def test_remove_allows_recomputation_of_an_existing_name_but_check_is_read_only(tmp_path):
    source=tmp_path/'source.ome.zarr';labeled_source(source)
    before=digest(source)
    preflight(source,tmp_path/'out',Settings(input_labels='remove'),[Prompt('target1','cell')])
    assert digest(source)==before and not (tmp_path/'out').exists()
    output=run(source,tmp_path/'out',Settings(input_labels='remove'),[Prompt('target1','cell')],predictor_factory=Mask)[0]
    result=zarr.open_group(str(output),mode='r')
    assert result['labels'].attrs['labels']==['wevisone_target1']
    assert int(result['labels/wevisone_target1/0'][:].max())==1
    assert int(zarr.open_group(str(source),mode='r')['labels/wevisone_target1/0'][:].max())==31


def test_keep_rejects_colliding_name_before_model_loading(tmp_path):
    source=tmp_path/'source.ome.zarr';labeled_source(source)
    def must_not_load(settings):pytest.fail('Model loaded before label-name validation')
    with pytest.raises(ValueError,match='already exists'):
        run(source,tmp_path/'out',Settings(input_labels='keep'),[Prompt('target1','cell')],predictor_factory=must_not_load)
    assert not (tmp_path/'out').exists()


def test_remove_still_checks_requested_channels_before_model_loading(tmp_path):
    source=tmp_path/'source.ome.zarr';labeled_source(source)
    def must_not_load(settings):pytest.fail('Model loaded before channel validation')
    with pytest.raises(ValueError,match='channel does not exist'):
        run(source,tmp_path/'out',Settings(input_labels='remove'),[Prompt('target1','cell',(2,))],predictor_factory=must_not_load)


@pytest.mark.parametrize('policy',['keep','remove'])
def test_policy_applies_to_every_hcs_field_and_timepoint(tmp_path,policy):
    field=tmp_path/'field.ome.zarr';labeled_source(field)
    source=tmp_path/'plate.ome.zarr'
    root=zarr.open_group(str(source),mode='w')
    root.attrs['plate']={'wells':[{'path':'A/1'}]}
    root.require_group('A/1').attrs['well']={'images':[{'path':'0'},{'path':'1'}]}
    for name in ('0','1'):shutil.copytree(field,source/'A/1'/name)
    before=digest(source)
    output=run(source,tmp_path/'out',Settings(input_labels=policy),[Prompt('fresh','cell')],predictor_factory=Mask)[0]
    result=zarr.open_group(str(output),mode='r')
    for name in ('0','1'):
        image=result[f'A/1/{name}']
        assert ('reference' in image['labels'])==(policy=='keep')
        assert image['labels/wevisone_fresh/0'].shape==(2,1,1,8,10)
    assert digest(source)==before


@pytest.mark.parametrize('policy',['keep','remove'])
@pytest.mark.parametrize('projection',['Max','Mean'])
def test_volume_ids_are_never_projected_or_removed_from_source(tmp_path,policy,projection):
    source=tmp_path/'volume.ome.zarr'
    pixels=labeled_source(source,z_planes=3)
    before=digest(source)
    output=run(source,tmp_path/'out',Settings(input_labels=policy,projection=projection),[Prompt('fresh','cell')],predictor_factory=Mask)[0]
    result=zarr.open_group(str(output),mode='r')
    assert 'reference' not in result['labels'] and 'wevisone_target1' not in result['labels']
    assert result['labels/wevisone_fresh/0'].shape==(2,1,1,8,10)
    expected=pixels.max(axis=2) if projection=='Max' else pixels.mean(axis=2).astype(np.float32)
    np.testing.assert_array_equal(result['0'][:],expected[:,:,None])
    assert digest(source)==before


def test_basic_label_options_are_available_through_cli_and_descriptor():
    from bilayers_cli import load_config
    args=build_parser().parse_args(['--infolder','input','--outfolder','output','--prompt-1','cell','--input-labels','remove'])
    settings,_=settings_from_args(args)
    assert settings.input_labels=='remove' and Settings().input_labels=='keep'
    config=load_config(Path(__file__).parents[1]/'config.yaml')
    for name in ('name_1','name_2','name_3','name_4','input_labels'):
        parameter=next(p for p in config['parameters'] if p['name']==name)
        assert parameter['mode']=='beginner' and parameter['section_id']=='essential'
