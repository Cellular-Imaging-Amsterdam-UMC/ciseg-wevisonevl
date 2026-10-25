import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest
import zarr

from ciseg_wevisonevl.engine import preflight, run
from ciseg_wevisonevl.outputs import replace_completed_run
from ciseg_wevisonevl.settings import Prompt, Settings
from tools.prepare_publicdata import write_store
from wrapper import build_parser, settings_from_args


class Mask:
    manifest = {'revision': 'test-only'}
    def __init__(self, settings):pass
    def predict(self, image, text):
        mask = np.zeros((image.height, image.width), np.float32)
        mask[1:3, 1:4] = 1 if text == 'old' else 0
        if text != 'old':mask[4:7, 5:9] = 1
        return SimpleNamespace(response='test', prompt=text, boxes=[], masks=[mask])


def digest(path):
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}


def initial(tmp_path):
    source = tmp_path/'source.ome.zarr'
    write_store(source, np.arange(80, dtype=np.uint16).reshape(8, 10), 'source')
    folder = tmp_path/'out'
    result = run(source, folder, Settings(), [Prompt('cell', 'old')], predictor_factory=Mask)[0]
    return source, folder, result


def test_overwrite_replaces_labels_and_csv_together_and_preserves_source(tmp_path):
    source, folder, old = initial(tmp_path)
    source_before = digest(source)
    (folder/'notes.txt').write_text('unrelated file')
    result = run(source, folder, Settings(overwrite=1), [Prompt('new', 'new')], predictor_factory=Mask)[0]
    assert result == old
    group = zarr.open_group(str(result), mode='r')
    assert 'wevisone_cell' not in group['labels']
    assert int(group['labels/wevisone_new/0'][0,0,0].sum()) == 12
    assert ',new,new,' in (folder/'measurements.csv').read_text(encoding='utf-8-sig')
    assert (folder/'notes.txt').read_text() == 'unrelated file'
    assert digest(source) == source_before
    assert not list(folder.glob('.wevisone-*'))
    assert json.loads((result/'wevisone-run.json').read_text())['settings']['overwrite'] == 1


def test_overwrite_check_input_is_read_only(tmp_path):
    source, folder, _ = initial(tmp_path)
    before = digest(folder)
    preflight(source, folder, Settings(overwrite=1), [Prompt('cell', 'new')])
    assert digest(folder) == before


def test_failed_prediction_keeps_previous_completed_results_and_csv(tmp_path):
    source, folder, old = initial(tmp_path)
    before, csv_before = digest(old), (folder/'measurements.csv').read_bytes()
    class Fails(Mask):
        def predict(self, *args):raise RuntimeError('inference failed')
    with pytest.raises(RuntimeError, match='inference failed'):
        run(source, folder, Settings(overwrite=1), [Prompt('cell', 'new')], predictor_factory=Fails)
    assert digest(old) == before and (folder/'measurements.csv').read_bytes() == csv_before
    assert list(folder.glob('.wevisone-run-*.partial'))


def test_failed_second_input_keeps_every_previous_output_and_csv(tmp_path):
    inputs = tmp_path/'inputs'; inputs.mkdir()
    for name in ('a', 'b'):write_store(inputs/(name+'.ome.zarr'), np.zeros((8, 10), np.uint8), name)
    folder = tmp_path/'out'
    outputs = run(inputs, folder, Settings(), [Prompt('cell', 'old')], predictor_factory=Mask)
    before = [digest(path) for path in outputs]
    csv_before = (folder/'measurements.csv').read_bytes()
    class FailsSecond(Mask):
        calls = 0
        def predict(self, image, text):
            self.calls += 1
            if self.calls == 2:raise RuntimeError('second input failed')
            return super().predict(image, text)
    with pytest.raises(RuntimeError, match='second input failed'):
        run(inputs, folder, Settings(overwrite=1), [Prompt('cell', 'new')], predictor_factory=FailsSecond)
    assert [digest(path) for path in outputs] == before
    assert (folder/'measurements.csv').read_bytes() == csv_before


def test_failed_publication_rolls_back_previous_store_and_measurements(tmp_path, monkeypatch):
    from ciseg_wevisonevl import outputs
    source, folder, old = initial(tmp_path)
    before, csv_before = digest(old), (folder/'measurements.csv').read_bytes()
    publish = outputs.publish_store
    def fail_csv_publication(partial, target):
        if partial.parent.name.startswith('.wevisone-run-') and partial.name == 'measurements.csv':
            raise PermissionError('publication blocked')
        return publish(partial, target)
    monkeypatch.setattr(outputs, 'publish_store', fail_csv_publication)
    with pytest.raises(PermissionError, match='publication blocked'):
        run(source, folder, Settings(overwrite=1), [Prompt('cell', 'new')], predictor_factory=Mask)
    assert digest(old) == before and (folder/'measurements.csv').read_bytes() == csv_before


def test_overwrite_preserves_input_output_separation(tmp_path):
    source = tmp_path/'source.ome.zarr'
    write_store(source, np.zeros((8, 10), np.uint8), 'source')
    before = digest(source)
    for output in (source, source/'results', source.parent):
        with pytest.raises(ValueError, match='separate'):
            preflight(source, output, Settings(overwrite=1), [Prompt('cell', 'new')])
    assert before == digest(source)


def test_refuses_replacement_of_foreign_folder(tmp_path):
    source = tmp_path/'source.ome.zarr'
    write_store(source, np.zeros((8, 10), np.uint8), 'source')
    foreign = tmp_path/'out/source__wevisonevl.ome.zarr'
    foreign.mkdir(parents=True); (foreign/'important.txt').write_text('keep')
    with pytest.raises(ValueError, match='without a CISegWeVisOneVL run report'):
        preflight(source, foreign.parent, Settings(overwrite=1), [Prompt('cell', 'new')])
    assert (foreign/'important.txt').read_text() == 'keep'


def test_staging_outside_output_is_rejected(tmp_path):
    folder = tmp_path/'out';folder.mkdir()
    staging = tmp_path/'.wevisone-run-external.partial';staging.mkdir()
    with pytest.raises(ValueError, match='inside the output'):
        replace_completed_run(staging, folder, ['measurements.csv'])


def test_cli_and_gui_overwrite_options(tmp_path, monkeypatch):
    from bilayers_cli import load_config
    parser = build_parser()
    settings, _ = settings_from_args(parser.parse_args(['--infolder','input','--outfolder','output','--prompt-1','cell','--overwrite','1']))
    assert settings.overwrite == 1 and Settings().overwrite == 0
    config = load_config(__import__('pathlib').Path(__file__).parents[1]/'config.yaml')
    option = next(p for p in config['parameters'] if p['name'] == 'overwrite')
    assert option['default'] == 1 and option['mode'] == 'advanced'
