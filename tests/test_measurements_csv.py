import csv
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
import zarr
from ciseg_wevisonevl.engine import run
from ciseg_wevisonevl.settings import Settings,Prompt
from tools.prepare_publicdata import write_store
from bilayers_cli import load_config,generate_cli_command


class KnownMask:
    manifest={'repo_id':'test-only','revision':'test'}
    def __init__(self,settings):pass
    def predict(self,image,text):
        if text=='absent':
            return SimpleNamespace(response='None',prompt=text,boxes=[],masks=[])
        mask=np.zeros((image.height,image.width),np.float32)
        mask[2:5,3:7]=1
        return SimpleNamespace(response='test',prompt=text,boxes=[],masks=[mask])


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:
        return list(csv.DictReader(stream))


def test_known_shape_and_every_channel_native_intensities(tmp_path):
    source=tmp_path/'in'/'rgb.ome.zarr';source.parent.mkdir()
    raw=np.arange(8*10*3,dtype=np.uint8).reshape(8,10,3)
    write_store(source,raw,'rgb',pixel_um=.5)
    run(source,tmp_path/'out',Settings(),[Prompt('tissue','tissue',(1,))],predictor_factory=KnownMask)
    rows=read_csv(tmp_path/'out/measurements.csv')
    assert len(rows)==1
    row=rows[0]
    assert row['input_store']=='rgb.ome.zarr' and row['output_store']=='rgb__wevisonevl.ome.zarr'
    assert row['area_px']=='12' and float(row['area_um2'])==3
    assert float(row['centroid_y_px'])==3 and float(row['centroid_x_px'])==4.5
    assert row['bbox_max_y_px_exclusive']=='5' and row['bbox_max_x_px_exclusive']=='7'
    assert float(row['solidity'])==1
    assert float(row['perimeter_px'])==10
    assert float(row['perimeter_um'])==5
    assert row['perimeter_um_method']=='scaled_pixel_estimator'
    assert float(row['centroid_y_um'])==1.5 and float(row['centroid_x_um'])==2.25
    assert float(row['bbox_min_y_um'])==1 and float(row['bbox_max_x_um_exclusive'])==3.5
    for feature in ['equivalent_diameter','major_axis_length','minor_axis_length']:
        assert float(row[feature+'_um'])==pytest.approx(float(row[feature+'_px'])*.5)
    assert row['shape_basis']=='physical_um'
    for c in range(3):
        pixels=raw[2:5,3:7,c]
        assert float(row[f'channel_{c+1}_min'])==pixels.min()
        assert float(row[f'channel_{c+1}_max'])==pixels.max()
        assert float(row[f'channel_{c+1}_mean'])==pixels.mean()
        assert float(row[f'channel_{c+1}_total'])==pixels.sum()
    with pytest.raises(FileExistsError,match='Measurements'):
        run(source,tmp_path/'out',Settings(),[Prompt('tissue','tissue')],predictor_factory=KnownMask)


def test_single_csv_across_inputs_different_channel_counts_and_empty_labels(tmp_path):
    folder=tmp_path/'in';folder.mkdir()
    write_store(folder/'a.ome.zarr',np.full((8,10),4,np.uint16),'a')
    write_store(folder/'b.ome.zarr',np.full((8,10,3),7,np.uint8),'b')
    run(folder,tmp_path/'out',Settings(),[Prompt('tissue','tissue'),Prompt('empty','absent')],predictor_factory=KnownMask)
    assert len(list((tmp_path/'out').glob('*.csv')))==1
    rows=read_csv(tmp_path/'out/measurements.csv')
    assert len(rows)==2
    assert rows[0]['channel_2_mean']=='' and float(rows[1]['channel_3_mean'])==7
    assert all(r['area_um2']=='' for r in rows)
    assert all(r['centroid_y_um']==r['perimeter_um']==r['major_axis_length_um']=='' for r in rows)
    assert all(r['shape_basis']=='pixels' for r in rows)
    assert {r['prompt_name'] for r in rows}=={'tissue'}


def test_four_fluorescence_channels_are_retained_and_all_measured(tmp_path,monkeypatch):
    from tools import curate_extra_publicdata as curate
    monkeypatch.setattr(curate,'READY',tmp_path)
    data=np.stack([np.full((8,10),v,np.uint16) for v in [3,7,11,101]])[None,:,None]
    source=curate.write_ngff('four-real-channels',data)
    np.testing.assert_array_equal(zarr.open_group(str(source),mode='r')['0'][:],data)
    run(source,tmp_path/'out',Settings(),[Prompt('tissue','tissue',(1,))],predictor_factory=KnownMask)
    row=read_csv(tmp_path/'out/measurements.csv')[0]
    assert float(row['channel_4_mean'])==101 and float(row['channel_4_total'])==12*101


def test_mean_projection_measurements_preserve_every_timepoint_and_channel(tmp_path):
    from test_projection_time import volume
    source=tmp_path/'volume.ome.zarr'
    raw=volume(source)
    run(source,tmp_path/'out',Settings(projection='Mean'),[Prompt('tissue','tissue')],predictor_factory=KnownMask)
    rows=read_csv(tmp_path/'out/measurements.csv')
    assert [r['time_index'] for r in rows]==['0','1']
    expected=raw.mean(axis=2).astype(np.float32)
    for t,row in enumerate(rows):
        assert row['projection']=='Mean' and row['source_z_planes']=='3'
        assert float(row['area_um2'])==pytest.approx(12*.4*.6)
        for c in range(2):
            assert float(row[f'channel_{c+1}_total'])==pytest.approx(expected[t,c,2:5,3:7].sum(dtype=np.float64))


def test_anisotropic_physical_shapes_and_positions(tmp_path):
    from test_projection_time import volume
    source=tmp_path/'anisotropic.ome.zarr';volume(source)
    run(source,tmp_path/'out',Settings(projection='Mean'),[Prompt('tissue','tissue')],predictor_factory=KnownMask)
    row=read_csv(tmp_path/'out/measurements.csv')[0]
    assert float(row['pixel_size_y_um'])==.4 and float(row['pixel_size_x_um'])==.6
    assert float(row['origin_y_um'])==11 and float(row['origin_x_um'])==12
    assert float(row['centroid_y_um'])==pytest.approx(12.2)
    assert float(row['centroid_x_um'])==pytest.approx(14.7)
    assert float(row['bbox_min_y_um'])==pytest.approx(11.8)
    assert float(row['bbox_max_x_um_exclusive'])==pytest.approx(16.2)
    assert float(row['major_axis_length_um'])==pytest.approx(4*np.sqrt(1.25*.6**2))
    assert float(row['minor_axis_length_um'])==pytest.approx(4*np.sqrt((2/3)*.4**2))
    assert float(row['equivalent_diameter_um'])==pytest.approx(np.sqrt(4*12*.4*.6/np.pi))
    expected_perimeter=2*(3*.6+2*.4)+4*np.hypot(.6/2,.4/2)
    assert float(row['perimeter_um'])==pytest.approx(expected_perimeter)
    assert row['perimeter_um_method']=='anisotropic_marching_squares'
    assert float(row['eccentricity'])!=pytest.approx(float(row['eccentricity_px']))


def test_composes_dataset_and_global_coordinate_transforms(tmp_path):
    from test_projection_time import volume
    source=tmp_path/'transformed.ome.zarr';volume(source)
    root=zarr.open_group(str(source),mode='a');ms=root.attrs['multiscales']
    ms[0]['coordinateTransformations']=[{'type':'scale','scale':[1,1,1,2,3]},{'type':'translation','translation':[0,0,0,100,200]}]
    root.attrs['multiscales']=ms
    run(source,tmp_path/'out',Settings(),[Prompt('tissue','tissue')],predictor_factory=KnownMask)
    row=read_csv(tmp_path/'out/measurements.csv')[0]
    assert float(row['pixel_size_y_um'])==pytest.approx(.8)
    assert float(row['pixel_size_x_um'])==pytest.approx(1.8)
    assert float(row['origin_y_um'])==122 and float(row['origin_x_um'])==236
    assert float(row['centroid_y_um'])==pytest.approx(124.4)
    assert float(row['centroid_x_um'])==pytest.approx(244.1)


def test_nanometer_calibration_exports_micrometers(tmp_path):
    source=tmp_path/'nano.ome.zarr';write_store(source,np.ones((8,10),np.uint8),'nano',pixel_um=.5)
    root=zarr.open_group(str(source),mode='a');ms=root.attrs['multiscales']
    for axis in ms[0]['axes']:
        if axis['name'] in ('y','x'):axis['unit']='nanometer'
    ms[0]['datasets'][0]['coordinateTransformations']=[{'type':'scale','scale':[1,1,1,500,500]},{'type':'translation','translation':[0,0,0,2500,7500]}]
    root.attrs['multiscales']=ms
    run(source,tmp_path/'out',Settings(),[Prompt('tissue','tissue')],predictor_factory=KnownMask)
    row=read_csv(tmp_path/'out/measurements.csv')[0]
    assert float(row['area_um2'])==3 and float(row['perimeter_um'])==5
    assert float(row['centroid_y_um'])==4 and float(row['centroid_x_um'])==9.75


def test_failed_run_leaves_no_completed_measurement_attachment(tmp_path):
    source=tmp_path/'in.ome.zarr'
    write_store(source,np.ones((8,10),np.uint8),'in')
    class Fails(KnownMask):
        def predict(self,*args):raise RuntimeError('model failed')
    with pytest.raises(RuntimeError,match='model failed'):
        run(source,tmp_path/'out',Settings(),[Prompt('tissue','tissue')],predictor_factory=Fails)
    assert not (tmp_path/'out/measurements.csv').exists()
    assert list((tmp_path/'out').glob('measurements.partial-*'))


def test_descriptor_declares_exact_csv_filename_as_measurement_attachment():
    config=load_config(Path(__file__).parents[1]/'config.yaml')
    assert config['citations'][0]['name']=='CISegWeVisOneVL'
    assert '3D' in config['citations'][0]['description'] and 'CSV' in config['citations'][0]['description']
    spec=next(o for o in config['outputs'] if o['name']=='measurements_csv_out')
    assert spec['type']=='measurement' and spec['format']==['csv']
    assert spec['unique_string']==['measurements.csv'] and spec['folder_name']=='/data/out'
    command=generate_cli_command(config,{'infolder':'in','outfolder':'out'})
    assert 'measurements.csv' not in command and 'None' not in command
