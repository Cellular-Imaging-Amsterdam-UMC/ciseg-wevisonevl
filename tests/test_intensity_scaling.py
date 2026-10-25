import csv
import hashlib
import json
import shutil
from types import SimpleNamespace

import numpy as np
import pytest
import zarr

from ciseg_wevisonevl.engine import preflight, run
from ciseg_wevisonevl.inference import render_rgb
from ciseg_wevisonevl.settings import Prompt, Settings
from tools.prepare_publicdata import write_store


def test_uint16_rgb_uses_shared_full_range_without_contrast_stretch():
    pixels = np.array([[[0, 32768, 65535]], [[0, 16384, 32768]], [[0, 8192, 16384]]], dtype=np.uint16)
    before = pixels.copy()
    image, limits = render_rgb(pixels, (1, 2, 3), "dtype")
    np.testing.assert_array_equal(np.asarray(image), [[[0, 0, 0], [128, 64, 32], [255, 128, 64]]])
    np.testing.assert_array_equal(pixels, before)
    assert all(row['low'] == 0 and row['high'] == 65535 for row in limits)


def test_metadata_uses_display_start_end_and_explicit_rgb_channel_order():
    planes = {0: np.array([[50, 100, 150, 200, 250]], np.uint16),
              1: np.array([[100, 200, 300, 400, 500]], np.uint16),
              2: np.array([[0, 10, 20, 30, 40]], np.uint16)}
    windows = {1: {'start': 100, 'end': 200, 'min': 0, 'max': 65535},
               2: {'start': 100, 'end': 500}, 3: {'start': 10, 'end': 30}}
    image, limits = render_rgb(planes, (3, 1, 2), 'metadata', windows=windows)
    np.testing.assert_array_equal(np.asarray(image), [[[0, 0, 0], [0, 0, 64], [128, 128, 128], [255, 255, 191], [255, 255, 255]]])
    assert limits == [{'channel': 3, 'low': 10, 'high': 30}, {'channel': 1, 'low': 100, 'high': 200}, {'channel': 2, 'low': 100, 'high': 500}]


@pytest.mark.parametrize('window', [None, {}, {'min': 0, 'max': 65535}, {'start': 4, 'end': 4},
    {'start': 5, 'end': 4}, {'start': 0, 'end': float('nan')}, {'start': 0, 'end': float('inf')},
    {'start': '0', 'end': 100}, {'start': False, 'end': 100}])
def test_invalid_metadata_fails_before_model_loading(tmp_path, window):
    source = tmp_path/'image.ome.zarr'
    write_store(source, np.ones((8, 10), np.uint16), 'image')
    root = zarr.open_group(str(source), mode='a')
    root.attrs['omero'] = {'channels': [{'window': window}]}
    def must_not_load(settings):
        pytest.fail('Model loaded before window validation')
    with pytest.raises(ValueError, match='window.start < window.end'):
        run(source, tmp_path/'out', Settings(normalization='metadata'), [Prompt('cell', 'cell')], predictor_factory=must_not_load)
    assert not (tmp_path/'out').exists()


def test_every_hcs_field_is_validated_and_unused_windows_are_ignored(tmp_path):
    source = tmp_path/'image.ome.zarr'
    write_store(source, np.ones((8, 10, 3), np.uint16), 'image')
    plate = tmp_path/'screen.ome.zarr'
    root = zarr.open_group(str(plate), mode='w')
    root.attrs['plate'] = {'wells': [{'path': 'A/1'}]}
    root.require_group('A/1').attrs['well'] = {'images': [{'path': '0'}, {'path': '1'}]}
    for field in ('0', '1'):
        shutil.copytree(source, plate/'A/1'/field)
        image = root[f'A/1/{field}']
        image.attrs['omero'] = {'channels': [{'window': {'start': 0, 'end': 100 if field == '0' else 200}}, {}, {}]}
    jobs = preflight(plate, tmp_path/'out', Settings(normalization='metadata'), [Prompt('cell', 'cell')])
    fields = jobs[0][2]
    assert [f.render_options('metadata', (1,))['windows'][1]['end'] for f in fields] == [100, 200]
    with pytest.raises(ValueError, match='Channel 2'):
        preflight(plate, tmp_path/'out', Settings(normalization='metadata'), [Prompt('cell', 'cell', (1, 2, 3))])
    root['A/1/1'].attrs['omero'] = {}
    with pytest.raises(ValueError, match='A/1/1'):
        preflight(plate, tmp_path/'out', Settings(normalization='metadata'), [Prompt('cell', 'cell')])


@pytest.mark.parametrize('normalization', ['dtype', 'metadata'])
@pytest.mark.parametrize('projection', ['Max', 'Mean'])
def test_uint16_rgb_projection_preserves_source_measurements_and_records_limits(tmp_path, normalization, projection):
    source = tmp_path/'rgb.ome.zarr'
    root = zarr.open_group(str(source), mode='w')
    raw = np.arange(2*3*2*8*10, dtype=np.uint16).reshape(2, 3, 2, 8, 10)+100
    root.create_dataset('0', data=raw)
    root.attrs['multiscales'] = [{'version': '0.4', 'axes': [{'name': a} for a in 'tczyx'], 'datasets': [{'path': '0'}]}]
    root.attrs['omero'] = {'channels': [{'window': {'start': 100*(c+1), 'end': 100*(c+1)+1000}} for c in range(3)]}
    def digest():
        return {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
    before = digest()
    class Capture:
        manifest = {'revision': 'test-only'}
        inputs = []
        def __init__(self, settings): pass
        def predict(self, image, text):
            self.inputs.append(np.asarray(image))
            mask = np.zeros((8, 10), np.float32); mask[2:5, 3:7] = 1
            return SimpleNamespace(response='test', prompt=text, boxes=[], masks=[mask])
    output = run(source, tmp_path/'out', Settings(normalization=normalization, projection=projection),
                 [Prompt('cell', 'cell', (1, 2, 3))], predictor_factory=Capture)[0]
    expected = raw.max(axis=2) if projection == 'Max' else raw.mean(axis=2).astype(np.float32)
    np.testing.assert_array_equal(zarr.open_group(str(output), mode='r')['0'][:], expected[:, :, None])
    assert before == digest()
    report = json.loads((output/'wevisone-run.json').read_text())
    assert [r['time_index'] for r in report['fields']] == [0, 1]
    assert [r['high'] for r in report['fields'][0]['normalization_limits']] == ([65535]*3 if normalization == 'dtype' else [1100, 1200, 1300])
    for t, image in enumerate(Capture.inputs):
        lo = np.array([0]*3 if normalization == 'dtype' else [100, 200, 300])[:, None, None]
        span = 65535 if normalization == 'dtype' else 1000
        rgb = np.rint(np.clip((expected[t].astype(float)-lo)/span, 0, 1)*255).astype(np.uint8).transpose(1, 2, 0)
        np.testing.assert_array_equal(image, rgb)
    with (tmp_path/'out/measurements.csv').open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    for t, row in enumerate(rows):
        for c in range(3):
            assert float(row[f'channel_{c+1}_mean']) == pytest.approx(expected[t, c, 2:5, 3:7].mean())


def test_float_source_requires_an_explicit_display_window_or_percentiles(tmp_path):
    source = tmp_path/'float.ome.zarr'
    write_store(source, np.ones((8, 10), np.float32), 'float')
    with pytest.raises(ValueError, match='unsigned integer source'):
        preflight(source, tmp_path/'out', Settings(normalization='dtype'), [Prompt('cell', 'cell')])
