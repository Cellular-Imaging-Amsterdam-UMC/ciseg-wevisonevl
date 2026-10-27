import csv,json
from types import SimpleNamespace
import numpy as np
import pytest
import zarr
from scipy import ndimage as ndi
from skimage.transform import resize_local_mean
from ciseg_wevisonevl.io import inspect_store
from ciseg_wevisonevl.overview import read_overview,select_level,smooth_label_block
from ciseg_wevisonevl.engine import run
from ciseg_wevisonevl.settings import Settings,Prompt
from tools.prepare_publicdata import write_store


def store(path,height=701,width=1301):
    write_store(path,np.full((height,width,3),7,np.uint8),'scan',pixel_um=.5)
    root=zarr.open_group(str(path),mode='a')
    ms=root.attrs['multiscales'];ms[0]['datasets']=ms[0]['datasets'][:1]
    for i,(h,w) in enumerate([(350,650),(175,325)],1):
        a=root.create_dataset(str(i),shape=(1,3,1,h,w),chunks=(1,1,1,128,128),dtype='u1',fill_value=7,overwrite=True)
        ms[0]['datasets'].append({'path':str(i),'coordinateTransformations':[{'type':'scale','scale':[1,1,1,.5*2**i,.5*2**i]}]})
    root.attrs['multiscales']=ms
    return inspect_store(path,[Prompt('a','a')],allow_large=True)[0]


def test_closest_level_above_bound_and_no_small_image_upscale(tmp_path):
    f=store(tmp_path/'scan.ome.zarr')
    assert select_level(f,512).dataset=='1'
    assert select_level(f,650).dataset=='1'
    assert select_level(f,4096).dataset=='0'
    planes,level=read_overview(f,512)
    assert planes[0].shape==(276,512)
    for plane in planes.values():np.testing.assert_allclose(plane,7)


def test_bounded_fractional_area_resampling_matches_reference(tmp_path,monkeypatch):
    from ciseg_wevisonevl import overview
    raw=np.arange(23*31,dtype=np.uint16).reshape(23,31)
    path=tmp_path/'scan.ome.zarr';write_store(path,raw,'test')
    field=inspect_store(path,[Prompt('a','a')])[0]
    original=overview.read_window;reads=[]
    def bounded(field,channels,time_index,projection,window):
        reads.append(window)
        assert window[2]-window[0]<=8 and window[3]-window[1]<=8
        return original(field,channels,time_index,projection,window)
    monkeypatch.setattr(overview,'read_window',bounded)
    from ciseg_wevisonevl.streaming import blocks
    monkeypatch.setattr(overview,'blocks',lambda shape:blocks(shape,8))
    planes,_=read_overview(field,17)
    expected=resize_local_mean(raw,planes[0].shape,preserve_range=True)
    np.testing.assert_allclose(planes[0],expected,rtol=1e-6)
    assert len(reads)>1


def test_signed_distance_labels_keep_ids_and_are_block_independent():
    labels=np.zeros((19,23),np.uint32)
    yy,xx=np.ogrid[:19,:23]
    labels[(yy-9)**2+(xx-8)**2<30]=5
    labels[(yy-10)**2+(xx-16)**2<15]=900
    shape=(113,157)
    complete=smooth_label_block(labels,shape,(0,0,*shape))
    parts=np.zeros(shape,np.uint32)
    from ciseg_wevisonevl.streaming import blocks
    for window in blocks(shape,27):
        y,x,y1,x1=window
        parts[y:y1,x:x1]=smooth_label_block(labels,shape,window)
    np.testing.assert_array_equal(parts,complete)
    assert set(np.unique(parts))=={0,5,900}
    assert ndi.label(parts==5)[1]==ndi.label(parts==900)[1]==1
    np.testing.assert_array_equal(smooth_label_block(labels,labels.shape,(0,0,*labels.shape)),labels)


def test_overview_measurements_scale_area_total_intensity_and_geometry(tmp_path,monkeypatch):
    path=tmp_path/'scan.ome.zarr';field=store(path)
    class Predictor:
        manifest={'revision':'test'}
        def __init__(self,settings):self.calls=0
        def predict(self,image,text):
            self.calls+=1
            assert self.calls==1 and image.size==(512,276)
            mask=np.zeros((276,512),np.float32);mask[20:60,50:100]=1
            return SimpleNamespace(masks=[mask],response='test',prompt=text,boxes=[])
    output=run(path,tmp_path/'out',Settings(max_side=512,normalization='dtype'),[Prompt('a','a',(1,2,3))],predictor_factory=Predictor)[0]
    with (tmp_path/'out/measurements.csv').open(encoding='utf-8-sig') as stream:row=next(csv.DictReader(stream))
    sy,sx=701/276,1301/512
    assert float(row['area_px'])==pytest.approx(2000*sy*sx)
    assert float(row['area_um2'])==pytest.approx(2000*sy*sx*.25)
    assert float(row['channel_3_total'])==pytest.approx(2000*7*sy*sx)
    assert float(row['channel_3_valid_pixels'])==pytest.approx(2000*sy*sx)
    assert float(row['channel_3_mean'])==float(row['channel_3_min'])==float(row['channel_3_max'])==7
    assert float(row['centroid_y_px'])==pytest.approx(40*sy-.5)
    assert float(row['bbox_max_x_px_exclusive'])==pytest.approx(100*sx)
    assert float(row['measurement_area_px'])==2000 and row['measurement_method']=='overview_scaled'
    from skimage.measure import regionprops
    labels=np.zeros((276,512),np.uint32);labels[20:60,50:100]=1
    expected=regionprops(labels,spacing=(sy,sx))[0]
    assert float(row['major_axis_length_px'])==pytest.approx(expected.axis_major_length)
    assert float(row['equivalent_diameter_px'])==pytest.approx(expected.equivalent_diameter_area)
    group=zarr.open_group(str(output),mode='r')['labels/wevisone_a']
    assert group['0'].shape==(1,1,1,701,1301)
    assert set(np.unique(group['0'][:]))=={0,1}
    report=json.loads((output/'wevisone-run.json').read_text())
    assert report['fields'][0]['pyramid_dataset']=='1'
    assert report['fields'][0]['measurement_scale_yx']==pytest.approx([sy,sx])


def test_removed_tile_parameters_cannot_silently_run(tmp_path):
    from wrapper import build_parser
    with pytest.raises(SystemExit):
        build_parser().parse_args(['--infolder','a','--outfolder','b','--processing-mode','tiled'])
    assert not any('tile' in name for name in Settings.__dataclass_fields__)


@pytest.mark.parametrize('causal,explicit',[(False,False),(True,False),(False,True)])
def test_bounded_attention_matches_full_attention_with_global_keys(causal,explicit):
    import torch
    from ciseg_wevisonevl.attention import bounded_attention
    torch.manual_seed(7)
    q=torch.randn(1,4,1103,8,dtype=torch.float64)
    k=torch.randn(1,2,1103,8,dtype=torch.float64)
    v=torch.randn_like(k)
    mask=None
    if explicit:
        mask=torch.zeros((1,1,1103,1103),dtype=torch.float64)
        mask[...,700:]=-10000
    module=SimpleNamespace(training=False,is_causal=causal)
    actual,_=bounded_attention(module,q,k,v,mask,scaling=.3)
    expected=torch.nn.functional.scaled_dot_product_attention(q,k.repeat_interleave(2,1),v.repeat_interleave(2,1),attn_mask=mask,is_causal=causal,scale=.3)
    torch.testing.assert_close(actual,expected.transpose(1,2),rtol=1e-10,atol=1e-10)


def test_automatic_gpu_profiles_and_actual_free_memory():
    from ciseg_wevisonevl.resolution import plan_resolution,GIB
    side,plan=plan_resolution((25000,54000),4096,14*GIB,24*GIB)
    assert side==3072 and plan['gpu_profile_side']==3072
    side,plan=plan_resolution((25000,54000),4096,35*GIB,47*GIB)
    assert side==4096 and plan['gpu_profile_side']==4096
    side,_=plan_resolution((25000,54000),4096,6*GIB,24*GIB)
    assert 128<=side<3072
    assert plan_resolution((25000,54000),1024,35*GIB,47*GIB)[0]==1024
    with pytest.raises(RuntimeError,match='12 GB'):
        plan_resolution((10000,10000),4096,3*GIB,12*GIB)


def test_oom_retries_whole_overview_and_measurements_use_actual_scale(tmp_path):
    import torch
    path=tmp_path/'scan.ome.zarr'
    write_store(path,np.full((512,512),11,np.uint8),'test')
    class MemoryLimited:
        manifest={'revision':'test'}
        def __init__(self,settings):self.calls=0
        def predict(self,image,text):
            self.calls+=1
            if self.calls==1:
                assert image.size==(256,256)
                raise torch.cuda.OutOfMemoryError('deliberate test budget')
            assert image.size==(128,128)
            mask=np.zeros((128,128),np.float32);mask[10:20,10:20]=1
            return SimpleNamespace(masks=[mask],response='test',prompt=text,boxes=[])
    output=run(path,tmp_path/'out',Settings(max_side=256),[Prompt('a','a')],predictor_factory=MemoryLimited)[0]
    report=json.loads((output/'wevisone-run.json').read_text())
    entry=report['fields'][0]
    assert entry['actual_side_limit']==128 and entry['measurement_scale_yx']==[4,4]
    assert entry['resolution_attempts']==[{'side_limit':256,'size_xy':[256,256],'status':'cuda_out_of_memory'}]
    with (tmp_path/'out/measurements.csv').open(encoding='utf-8-sig') as stream:row=next(csv.DictReader(stream))
    assert float(row['area_px'])==1600 and float(row['channel_1_total'])==17600

