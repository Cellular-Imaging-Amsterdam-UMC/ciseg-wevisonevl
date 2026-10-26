from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import csv
import json
import numpy as np
import pytest
import zarr
from scipy import ndimage as ndi
from skimage.measure import regionprops

from ciseg_wevisonevl.engine import run,preflight
from ciseg_wevisonevl.io import Field,inspect_store
from ciseg_wevisonevl.settings import Settings,Prompt
from ciseg_wevisonevl.disk_stitch import DiskStitcher,windows
from ciseg_wevisonevl.streaming import read_window
from gui.image_data import load_frame


def image_store(path,shape=(1025,1301),huge=False):
    root=zarr.open_group(str(path),mode='w')
    array=root.create_dataset('0',shape=(1,1,1,*shape),chunks=(1,1,1,256,256),dtype='u2')
    if not huge:
        data=np.zeros(shape,np.uint16)
        data[20:960,100:300]=30000
        data[400:800,700:1250]=60000
        array[0,0,0]=data
    root.attrs['multiscales']=[{'version':'0.4','axes':[{'name':a,'type':'space' if a in 'zyx' else 'channel' if a=='c' else 'time',**({'unit':'micrometer'} if a in 'yx' else {})} for a in 'tczyx'],
                               'datasets':[{'path':'0','coordinateTransformations':[{'type':'scale','scale':[1,1,1,.4,.6]},{'type':'translation','translation':[0,0,0,11,12]}]}]}]
    return array


class Components:
    manifest={'revision':'test-only'}
    def __init__(self,settings):pass
    def predict(self,image,text):
        labels,n=ndi.label(np.asarray(image)[...,0]>80)
        masks=[(labels==i).astype(np.float32) for i in range(1,n+1)]
        return SimpleNamespace(response='test',prompt=text,boxes=[],masks=masks)


def test_tiled_seams_streamed_measurements_and_pyramids(tmp_path,monkeypatch):
    source=tmp_path/'source.zarr'
    original=np.asarray(image_store(source)[0,0,0])
    settings=Settings(processing_mode='tiled',tile_size=512,tile_overlap=128,max_side=512,normalization='dtype')
    def forbidden(*args,**kwargs):raise AssertionError('Full field read is forbidden')
    monkeypatch.setattr(Field,'pixels',forbidden)
    output=run(source,tmp_path/'out',settings,[Prompt('a','tissue'),Prompt('b','tissue')],predictor_factory=Components)[0]
    root=zarr.open_group(str(output),mode='r')
    actual=root['labels/wevisone_a/0'][0,0,0]
    expected,_=ndi.label(original>0)
    np.testing.assert_array_equal(actual>0,original>0)
    for region in regionprops(expected):
        assert len(np.unique(actual[expected==region.label]))==1
    assert len(np.unique(actual))==3
    np.testing.assert_array_equal(root['labels/wevisone_a/1'][0,0,0],actual[::2,::2])
    np.testing.assert_array_equal(root['0'][0,0,0],original)
    with (output.parent/'measurements.csv').open(encoding='utf-8-sig') as stream:
        rows=list(csv.DictReader(stream))
    assert len(rows)==4
    for row in rows[:2]:
        region=regionprops(actual)[int(row['label_id'])-1]
        metric=regionprops(actual,spacing=(.4,.6))[int(row['label_id'])-1]
        assert int(row['area_px'])==region.area
        assert float(row['area_um2'])==pytest.approx(region.area*.24)
        assert float(row['centroid_y_um'])==pytest.approx(region.centroid[0]*.4+11)
        for name,expected_value in [('major_axis_length_px',region.axis_major_length),('minor_axis_length_um',metric.axis_minor_length),('orientation_rad',metric.orientation),('eccentricity',metric.eccentricity)]:
            assert float(row[name])==pytest.approx(expected_value,abs=1e-6)
        pixels=original[actual==int(row['label_id'])]
        assert float(row['channel_1_total'])==pixels.astype(np.float64).sum()
        assert float(row['channel_1_mean'])==pytest.approx(pixels.mean())
        assert row['solidity']=='' and row['perimeter_um_method']=='streamed_pixel_edges'
        h,w=region.image.shape
        assert float(row['perimeter_px'])==2*(h+w)
        assert float(row['perimeter_um'])==pytest.approx(2*(h*.4+w*.6))
    report=json.loads((output/'wevisone-run.json').read_text())
    assert report['fields'][0]['stitched_matches']>0
    assert report['fields'][0]['retained_instances']==2
    assert not list(output.glob('.tiles_*'))


def test_min_area_applies_after_seam_merge_and_semantic_union(tmp_path):
    shape=(80,120)
    directory=tmp_path/'stitch';directory.mkdir()
    result=zarr.open_array(str(tmp_path/'target.zarr'),mode='w',shape=(1,1,1,*shape),chunks=(1,1,1,32,32),dtype='u4')
    stitch=DiskStitcher(directory,shape,.5)
    for window in windows(shape,64,24):
        y,x,y1,x1=window
        data=np.zeros(shape,np.uint32);data[30:40,10:110]=1
        stitch.add(window,data[y:y1,x:x1])
    count,area=stitch.finish(result,0,min_area=900)
    stitch.close()
    assert count==1 and area==1000
    assert np.count_nonzero(result[:])==1000


def test_large_guard_and_bounded_view_without_existing_pyramid(tmp_path,monkeypatch):
    source=tmp_path/'huge.ome.zarr'
    image_store(source,(4097,4099),huge=True)
    prompt=Prompt('a','tissue')
    with pytest.raises(ValueError,match='16 megapixels'):
        preflight(source,tmp_path/'out',Settings(),[prompt])
    assert preflight(source,tmp_path/'out',Settings(processing_mode='tiled'),[prompt])
    field=inspect_store(source,[],allow_large=True)[0]
    def forbidden(*args,**kwargs):raise AssertionError('Full field read is forbidden')
    monkeypatch.setattr(Field,'pixels',forbidden)
    frame=load_frame(field,0,(1,),'dtype','Max')
    assert max(frame['rgb'].shape[:2])<=2048
    assert frame['native_scale_yx']==(3,3)
    assert any('Overview' in note for note in frame['notes'])


@pytest.mark.parametrize('kwargs',[{'tile_size':8192},{'tile_overlap':2048},{'tile_match_threshold':0},{'processing_mode':'auto'},{'skip_blank_tiles':2}])
def test_invalid_tiling_settings(kwargs):
    with pytest.raises(ValueError):Settings(**kwargs).validate([Prompt('a','a')])


def test_failed_tile_preserves_completed_results(tmp_path):
    source=tmp_path/'source.ome.zarr';image_store(source,(300,400))
    settings=Settings(processing_mode='tiled',tile_size=256,tile_overlap=64,max_side=256,normalization='dtype',overwrite=1)
    output=run(source,tmp_path/'out',settings,[Prompt('a','a')],predictor_factory=Components)[0]
    previous=(output/'wevisone-run.json').read_bytes()
    class Failure(Components):
        def predict(self,image,text):raise RuntimeError('Deliberate tile failure')
    with pytest.raises(RuntimeError,match='Deliberate'):
        run(source,tmp_path/'out',settings,[Prompt('a','a')],predictor_factory=Failure)
    assert (output/'wevisone-run.json').read_bytes()==previous
    failed=[p for p in (tmp_path/'out').rglob('wevisone-run.json') if p!=output/'wevisone-run.json']
    report=json.loads(failed[0].read_text())
    assert report['status']=='failed' and report['fields'][0]['active_tile']['tile']==1


@pytest.mark.parametrize('method',['Max','Mean'])
@pytest.mark.parametrize('axes',['tczyx','tczxy'])
def test_tiled_projection_every_timepoint_and_axis_order(tmp_path,monkeypatch,method,axes):
    from test_projection_time import volume
    source=tmp_path/'source.ome.zarr'
    original=volume(source,axes,height=513,width=517)
    monkeypatch.setattr(Field,'pixels',lambda *a,**kw:pytest.fail('Whole-plane reader used'))
    output=run(source,tmp_path/'out',Settings(processing_mode='tiled',projection=method,tile_size=512,tile_overlap=128,max_side=512,normalization='dtype'),
               [Prompt('a','a')],predictor_factory=Components)[0]
    root=zarr.open_group(str(output),mode='r')
    expected=original.max(axis=2) if method=='Max' else original.mean(axis=2).astype(np.float32)
    np.testing.assert_array_equal(root['0'][:,:,0],expected)
    from ciseg_wevisonevl.projection import area_downsample
    for t in range(2):
        np.testing.assert_array_equal(root['1'][t,0,0],area_downsample(expected[t,0]))
    report=json.loads((output/'wevisone-run.json').read_text())
    assert [r['time_index'] for r in report['fields']]==[0,1]


def test_semantic_and_blank_tiles(tmp_path):
    source=tmp_path/'blank.ome.zarr'
    image_store(source,(300,400),huge=True)
    settings=Settings(processing_mode='tiled',tile_size=256,tile_overlap=64,normalization='dtype',skip_blank_tiles=1,label_mode='semantic')
    class Forbidden(Components):
        def predict(self,*args):pytest.fail('Blank tile reached predictor')
    output=run(source,tmp_path/'out',settings,[Prompt('a','a')],predictor_factory=Forbidden)[0]
    report=json.loads((output/'wevisone-run.json').read_text())
    assert report['fields'][0]['skipped_tiles']==4
    assert report['fields'][0]['retained_instances']==0
    # Semantic mode merges independently detected objects within this prompt only.
    second=tmp_path/'two.ome.zarr';image_store(second)
    output=run(second,tmp_path/'out2',replace(settings,skip_blank_tiles=0,max_side=256),[Prompt('a','a')],predictor_factory=Components)[0]
    labels=zarr.open_group(str(output),mode='r')['labels/wevisone_a/0'][0,0,0]
    assert set(np.unique(labels))=={0,1}


def test_existing_overview_and_odd_label_pyramid_align(tmp_path):
    source=tmp_path/'source.ome.zarr';image_store(source,(2051,2501),huge=True)
    root=zarr.open_group(str(source),mode='a')
    root.create_dataset('1',shape=(1,1,1,1025,1250),chunks=(1,1,1,128,128),dtype='u2')
    ms=root.attrs['multiscales']
    ms[0]['datasets'].append({'path':'1','coordinateTransformations':[{'type':'scale','scale':[1,1,1,.8,1.2]}]})
    root.attrs['multiscales']=ms
    field=inspect_store(source,[])[0]
    from ciseg_wevisonevl.tiled import label_group
    group=label_group(source,field,Prompt('a','a'),0)
    # Nearest label levels use ceil rather than the input's floor dimensions.
    group['1'][0,0,0,20,40]=9
    frame=load_frame(field,0,(1,),'dtype','Max')
    assert frame['rgb'].shape[:2]==(1025,1250)
    assert frame['labels']['wevisone_a'].shape==(1025,1250)
    assert frame['labels']['wevisone_a'][20,40]==9
    assert frame['native_scale_yx']==(2,2)


def test_disk_stitching_keeps_touching_objects_separate(tmp_path):
    truth=np.zeros((100,160),np.uint32)
    truth[15:70,40:80]=1;truth[15:70,80:120]=2
    work=tmp_path/'scratch';work.mkdir()
    stitch=DiskStitcher(work,truth.shape)
    target=zarr.open_array(str(tmp_path/'out.zarr'),mode='w',shape=(1,1,1,*truth.shape),chunks=(1,1,1,32,32),dtype='u4')
    for window in windows(truth.shape,96,32):
        y,x,y1,x1=window;stitch.add(window,truth[y:y1,x:x1])
    count,_=stitch.finish(target,0)
    stitch.close()
    assert count==2 and target[0,0,0,30,70]!=target[0,0,0,30,90]


def test_disk_ambiguous_split_is_retained_and_flagged(tmp_path):
    work=tmp_path/'scratch';work.mkdir()
    stitch=DiskStitcher(work,(40,80),.45)
    old=np.zeros((40,60),np.uint32);old[5:35,20:60]=1
    new=np.zeros((40,60),np.uint32);new[5:35,:20]=1;new[5:35,20:40]=2
    stitch.add((0,0,40,60),old);stitch.add((0,20,40,80),new)
    assert stitch.ambiguous==2 and stitch.matches==0
    stitch.close()


def test_cli_and_descriptor_expose_tiling():
    from bilayers_cli import load_config,generate_cli_command
    from wrapper import build_parser,settings_from_args
    import shlex
    command=generate_cli_command(load_config(),{'infolder':'input','outfolder':'out','prompt_1':'tissue',
                                              'processing_mode':'tiled','tile_size':4096,'tile_overlap':512})
    values=shlex.split(command)[2:]
    settings,prompts=settings_from_args(build_parser().parse_args(values))
    assert settings.processing_mode=='tiled' and settings.tile_size==4096 and settings.tile_overlap==512


def test_tiled_hcs_fields_remain_independent(tmp_path):
    source=tmp_path/'plate.ome.zarr'
    plate=zarr.open_group(str(source),mode='w')
    plate.require_group('A/1')
    for path in ['A/1/0','A/1/1']:
        image_store(source/path,(300,400))
    plate=zarr.open_group(str(source),mode='a')
    plate.attrs['plate']={'version':'0.4','wells':[{'path':'A/1'}]}
    plate['A/1'].attrs['well']={'images':[{'path':'0'},{'path':'1'}]}
    output=run(source,tmp_path/'out',Settings(processing_mode='tiled',tile_size=256,tile_overlap=64,normalization='dtype'),
               [Prompt('a','a')],predictor_factory=Components)[0]
    root=zarr.open_group(str(output),mode='r')
    assert root['A/1/0/labels/wevisone_a/0'].shape==(1,1,1,300,400)
    assert root['A/1/1/labels/wevisone_a/0'].shape==(1,1,1,300,400)
    report=json.loads((output/'wevisone-run.json').read_text())
    assert [r['field'] for r in report['fields']]==['A/1/0','A/1/1']


def test_plain_zarr_and_ome_alias_are_not_processed_twice(tmp_path):
    from ciseg_wevisonevl.io import discover
    source=tmp_path/'scan.zarr';image_store(source,(20,30))
    try:
        (tmp_path/'scan.ome.zarr').symlink_to(source,target_is_directory=True)
    except OSError:
        pytest.skip('Creating symlinks is unavailable on this host')
    assert discover(tmp_path)==[source.resolve()]


def test_overview_does_not_reinterpret_downsampled_time_or_z(tmp_path):
    from ciseg_wevisonevl.streaming import overview_field
    source=tmp_path/'source.ome.zarr';image_store(source,(2050,2500),huge=True)
    root=zarr.open_group(str(source),mode='a')
    root.create_dataset('0',shape=(2,1,3,2050,2500),chunks=(1,1,1,128,128),dtype='u2',overwrite=True)
    root.create_dataset('1',shape=(2,1,1,1025,1250),chunks=(1,1,1,128,128),dtype='u2')
    ms=root.attrs['multiscales'];ms[0]['datasets'].append({'path':'1'})
    root.attrs['multiscales']=ms
    field=inspect_store(source,[])[0]
    assert overview_field(field,2048) is None


def test_streamed_oblique_shape_and_nonfinite_intensities(tmp_path):
    from ciseg_wevisonevl.measurements import MeasurementCSV
    from ciseg_wevisonevl.stream_measurements import add_streamed
    source=tmp_path/'source.ome.zarr';image_store(source,(701,803),huge=True)
    root=zarr.open_group(str(source),mode='a')
    yy,xx=np.indices((701,803),dtype=np.float64)
    mask=(((yy-350)-.4*(xx-400))/110)**2+((xx-400)/270)**2<1
    pixels=(yy+xx/2).astype(np.float32);pixels[330:350,390:410]=np.nan
    root.create_dataset('0',data=pixels[None,None,None],chunks=(1,1,1,128,128),overwrite=True)
    field=inspect_store(source,[])[0]
    labels=zarr.open_array(str(tmp_path/'labels.zarr'),mode='w',shape=(1,1,1,701,803),chunks=(1,1,1,128,128),dtype='u4')
    labels[0,0,0]=mask
    prompt=Prompt('a','a')
    with MeasurementCSV(tmp_path/'out',1) as table:
        add_streamed(table,labels,field,prompt,field,0,Settings(processing_mode='tiled'),'out.ome.zarr',tmp_path/'stats.sqlite')
    with (tmp_path/'out/measurements.csv').open(encoding='utf-8-sig') as f:
        row=next(csv.DictReader(f))
    physical=regionprops(mask.astype(np.uint32),spacing=(.4,.6))[0]
    assert float(row['major_axis_length_um'])==pytest.approx(physical.axis_major_length,rel=1e-10)
    assert float(row['orientation_rad'])==pytest.approx(physical.orientation,abs=1e-10)
    values=pixels[mask];values=values[np.isfinite(values)]
    assert int(row['channel_1_valid_pixels'])==len(values)
    assert float(row['channel_1_mean'])==pytest.approx(values.astype(np.float64).mean())
    assert float(row['channel_1_min'])==values.min()
    assert float(row['channel_1_max'])==values.max()
