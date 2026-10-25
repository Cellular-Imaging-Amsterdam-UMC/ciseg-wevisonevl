import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import json
import sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
import zarr
from PyQt6.QtCore import QEventLoop, QProcess, QTimer, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication

from ciseg_wevisonevl.engine import run
from ciseg_wevisonevl.io import inspect_store
from ciseg_wevisonevl.settings import Prompt, Settings
from gui.image_data import load_frame, label_rgba
from gui.gui_wevisonevl import Window
from gui.viewer import ImageViewer
from tools.prepare_publicdata import write_store


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def wait_until(app, condition):
    if condition():return
    loop = QEventLoop()
    poll = QTimer(); poll.setInterval(20)
    poll.timeout.connect(lambda: loop.quit() if condition() else None)
    deadline = QTimer(); deadline.setSingleShot(True); deadline.timeout.connect(loop.quit)
    poll.start(); deadline.start(10000); loop.exec(); poll.stop(); deadline.stop()
    app.processEvents()
    assert condition(), 'GUI operation did not complete'


class Mask:
    manifest = {'revision': 'test-only'}
    def __init__(self, settings):pass
    def predict(self, image, text):
        plane = np.zeros((image.height, image.width), np.float32); plane[2:5, 3:7] = 1
        return SimpleNamespace(response='test', prompt=text, boxes=[], masks=[plane])


def completed_output(tmp_path):
    source = tmp_path/'source.ome.zarr'
    write_store(source, np.full((8, 10, 3), 32768, np.uint16), 'source')
    output = run(source, tmp_path/'out', Settings(normalization='dtype'),
                 [Prompt('cells', 'cells', (1, 2, 3)), Prompt('overlap', 'overlap')], predictor_factory=Mask)[0]
    return source, output


def test_viewer_loads_independent_labels_and_controls_visibility(tmp_path, app):
    source, output = completed_output(tmp_path)
    window = Window(state_path=tmp_path/'state.json')
    window.input_path.setText(str(output))
    window.widgets['normalization'].setCurrentIndex(window.widgets['normalization'].findData('dtype'))
    window.show()
    try:
        wait_until(app, lambda: window.layer_list.count() == 2)
        assert window.viewer.image_item.pixmap().size().width() == 10
        assert set(window.viewer.layers) == {'wevisone_cells', 'wevisone_overlap'}
        window.layer_list.item(0).setCheckState(Qt.CheckState.Unchecked)
        assert not window.viewer.layers['wevisone_cells'].isVisible()
        assert window.viewer.layers['wevisone_overlap'].isVisible()
        window.opacity.setValue(27)
        assert window.viewer.layers['wevisone_overlap'].opacity() == pytest.approx(.27)
        window.pixel_hovered(4, 3)
        assert 'overlap: 1' in window.status.text() and 'cells: 1' not in window.status.text()
        window.show_labels.setChecked(False)
        assert not any(item.isVisible() for item in window.viewer.layers.values())
        window.viewer.actual_size()
        assert window.viewer.transform().m11() == 1
        window.viewer.fit_image()
        assert window.viewer.auto_fit
    finally:
        window.close()


def test_completed_run_switches_single_viewer_to_saved_output(tmp_path, app):
    source, output = completed_output(tmp_path)
    window = Window(state_path=tmp_path/'state.json')
    window.input_path.setText(str(source))
    app.processEvents()
    window.preflight_run = False; window.running_output = output.parent
    window.finished(0, QProcess.ExitStatus.NormalExit)
    try:
        wait_until(app, lambda: window.layer_list.count() == 2)
        assert window.selected_store == output
        assert window.run_button.isEnabled()
        assert window.view_mode.currentIndex() == 0
    finally:
        window.close()


def test_invalid_display_settings_clear_stale_image_and_labels(tmp_path, app):
    _, output = completed_output(tmp_path)
    window = Window(state_path=tmp_path/'state.json')
    window.input_path.setText(str(output))
    window.widgets['normalization'].setCurrentIndex(window.widgets['normalization'].findData('dtype'))
    try:
        wait_until(app, lambda: window.layer_list.count() == 2)
        # A constant source has equal saved window limits and cannot use metadata scaling.
        window.widgets['normalization'].setCurrentIndex(window.widgets['normalization'].findData('metadata'))
        wait_until(app, lambda: 'window.start < window.end' in window.view_status.text())
        assert window.layer_list.count() == 0
        assert window.viewer.image_item.pixmap().isNull()
    finally:
        window.close()


def test_gui_runs_real_metadata_preflight_subprocess(tmp_path, app):
    source = tmp_path/'source.ome.zarr'
    write_store(source, np.arange(80, dtype=np.uint16).reshape(8, 10), 'source')
    window = Window(state_path=tmp_path/'state.json')
    window.input_path.setText(str(source)); window.output_path.setText(str(tmp_path/'out'))
    window.widgets['prompt_1'].setText('cell')
    window.widgets['normalization'].setCurrentIndex(window.widgets['normalization'].findData('metadata'))
    try:
        window.start(True)
        wait_until(app, lambda: window.run_button.isEnabled())
        assert window.process.exitCode() == 0, window.log.toPlainText()
        assert '"valid": true' in window.log.toPlainText()
        assert not (tmp_path/'out').exists()
        saved = json.loads((tmp_path/'state.json').read_text())
        assert saved['values']['normalization'] == 'metadata'
    finally:
        window.close()


def test_volume_labels_are_sliced_and_never_projected(tmp_path):
    source = tmp_path/'volume.ome.zarr'
    root = zarr.open_group(str(source), mode='w')
    pixels = np.stack([np.full((8, 10), 100, np.uint16), np.full((8, 10), 500, np.uint16)])[None, None]
    root.create_dataset('0', data=pixels)
    ms = {'version': '0.4', 'axes': [{'name': a} for a in 'tczyx'], 'datasets': [{'path': '0'}]}
    root.attrs['multiscales'] = [ms]
    labels = np.ones(pixels.shape, np.uint32); labels[:, :, 1] = 7
    root.create_dataset('labels/reference/0', data=labels)
    root['labels'].attrs['labels'] = ['reference']
    root['labels/reference'].attrs['multiscales'] = [ms]
    field = inspect_store(source, [])[0]
    projected = load_frame(field, 0, (1,), 'dtype', 'Max')
    assert not projected['labels'] and projected['notes']
    section = load_frame(field, 0, (1,), 'dtype', 'Max', 1)
    assert np.all(section['labels']['reference'] == 7)
    assert np.all(section['rgb'] == 2)


def test_mean_result_view_retains_unsigned_source_range(tmp_path):
    source = tmp_path/'volume.ome.zarr'
    root = zarr.open_group(str(source), mode='w')
    pixels = np.array([np.zeros((8, 10), np.uint16), np.full((8, 10), 65535, np.uint16)])[None, None]
    root.create_dataset('0', data=pixels)
    root.attrs['multiscales'] = [{'version': '0.4', 'axes': [{'name': a} for a in 'tczyx'], 'datasets': [{'path': '0'}]}]
    output = run(source, tmp_path/'out', Settings(normalization='dtype', projection='Mean'), [Prompt('cell', 'cell')], predictor_factory=Mask)[0]
    frame = load_frame(inspect_store(output, [])[0], 0, (1,), 'dtype', 'Max')
    assert np.all(frame['rgb'] == 128)
    assert frame['limits'][0]['high'] == 65535


def test_instance_overlay_background_is_transparent_and_colors_are_stable():
    plane = np.array([[0, 1, 20]], np.uint32)
    rgba = label_rgba(plane)
    assert rgba[0, :, 3].tolist() == [0, 255, 255]
    assert not np.array_equal(rgba[0, 1, :3], rgba[0, 2, :3])
    np.testing.assert_array_equal(rgba, label_rgba(plane))


def test_single_prompt_color_is_shared_by_instances_and_retains_transparent_background():
    labels = np.array([[0, 1, 4, 100]], np.uint32)
    before = labels.copy()
    rgba = label_rgba(labels, mode='single', color='#12abef')
    np.testing.assert_array_equal(rgba[0, 1:, :3], [[18, 171, 239]]*3)
    assert rgba[0, :, 3].tolist() == [0, 255, 255, 255]
    np.testing.assert_array_equal(labels, before)


def test_single_prompt_colors_stay_distinct_after_prior_dataset_preferences(app):
    viewer = ImageViewer()
    viewer.set_layer_style('existing', color='#ff5a9d')
    for index in range(5):viewer.set_layer_style(f'previous-{index}')
    plane = np.array([[1, 2]], np.uint32)
    viewer.set_frame(np.zeros((1, 2, 3), np.uint8), {'existing': plane, 'new-prompt': plane})
    assert viewer.layer_style('existing')['color'] != viewer.layer_style('new-prompt')['color']
    assert viewer.layers['existing'].pixmap().toImage().pixelColor(0, 0) != viewer.layers['new-prompt'].pixmap().toImage().pixelColor(0, 0)
    viewer.close()


def test_selecting_an_existing_prompt_color_keeps_visible_prompts_distinct(app):
    viewer = ImageViewer()
    plane = np.array([[1, 2]], np.uint32)
    viewer.set_frame(np.zeros((1, 2, 3), np.uint8), {'epidermis': plane, 'dermis': plane})
    chosen = viewer.layer_style('epidermis')['color']
    viewer.set_layer_style('dermis', color=chosen)
    assert viewer.layer_style('dermis')['color'] == chosen
    assert viewer.layer_style('epidermis')['color'] != chosen
    assert viewer.layers['dermis'].pixmap().toImage().pixelColor(0, 0).name() == chosen
    np.testing.assert_array_equal(viewer.label_arrays['epidermis'], plane)
    viewer.close()


def test_per_prompt_color_controls_do_not_reload_image_or_change_other_labels(tmp_path, app, monkeypatch):
    _, output = completed_output(tmp_path)
    window = Window(state_path=tmp_path/'state.json')
    window.input_path.setText(str(output))
    window.widgets['normalization'].setCurrentIndex(window.widgets['normalization'].findData('dtype'))
    try:
        wait_until(app, lambda: window.layer_list.count() == 2)
        a, b = 'wevisone_cells', 'wevisone_overlap'
        assert window.viewer.layer_style(a)['mode'] == window.viewer.layer_style(b)['mode'] == 'single'
        assert window.viewer.layers[a].pixmap().toImage().pixelColor(4, 3) != window.viewer.layers[b].pixmap().toImage().pixelColor(4, 3)
        initial_generation = window.generation
        background_key = window.viewer.image_item.pixmap().cacheKey()
        label_pixels = {name: labels.copy() for name, labels in window.viewer.label_arrays.items()}
        window.layer_list.setCurrentRow(0)
        window.label_color_mode.setCurrentIndex(window.label_color_mode.findData('instances'))
        assert window.viewer.layer_style(a)['mode'] == 'instances'
        assert window.viewer.layer_style(b)['mode'] == 'single'
        assert not window.label_color_button.isEnabled()
        window.layer_list.setCurrentRow(1)
        assert window.label_color_button.isEnabled()
        monkeypatch.setattr('gui.gui_wevisonevl.QColorDialog.getColor', lambda *args: QColor('#2def48'))
        window.choose_label_color()
        assert window.viewer.layers[b].pixmap().toImage().pixelColor(4, 3).name() == '#2def48'
        assert window.viewer.layer_style(a)['mode'] == 'instances'
        assert window.generation == initial_generation
        assert window.viewer.image_item.pixmap().cacheKey() == background_key
        for name, before in label_pixels.items():np.testing.assert_array_equal(window.viewer.label_arrays[name], before)
        window.layer_list.item(1).setCheckState(Qt.CheckState.Unchecked)
        window.label_color_mode.setCurrentIndex(window.label_color_mode.findData('instances'))
        assert not window.viewer.layers[b].isVisible()
    finally:
        window.close()


def test_identical_prompt_channels_share_one_background_choice(tmp_path, app):
    window = Window(state_path=tmp_path/'state.json')
    try:
        for slot in (1, 2):
            window.widgets[f'prompt_{slot}'].setText('tissue')
            window.widgets[f'channels_{slot}'].setText('1,2,3')
        assert window.background_channels.count() == 1
        assert window.background_channels.currentData() == (1, 2, 3)
        assert window.background_channels.currentText() == 'RGB: 1,2,3'
        assert not window.background_channels.isEnabled()
        window.widgets['channels_2'].setText('2')
        assert window.background_channels.count() == 2 and window.background_channels.isEnabled()
        assert window.background_channels.itemData(1) == (2,)
    finally:
        window.close()


def test_label_display_preferences_restore_without_changing_saved_run_parameters(tmp_path, app):
    state_path = tmp_path/'state.json'
    state_path.write_text(json.dumps({'input': 'saved-input', 'output': 'saved-output', 'values': {'prompt_1': 'saved prompt'}}))
    window = Window(state_path=state_path)
    window.viewer.set_layer_style('wevisone_cells', mode='instances', color='#20aa80')
    window.layer_checks['wevisone_cells'] = False
    window.opacity.setValue(31)
    window.close()
    state = json.loads(state_path.read_text())
    assert state['input'] == 'saved-input' and state['output'] == 'saved-output'
    assert state['values'] == {'prompt_1': 'saved prompt'}
    reopened = Window(state_path=state_path)
    try:
        assert reopened.viewer.layer_style('wevisone_cells') == {'mode': 'instances', 'color': '#20aa80'}
        assert not reopened.layer_checks['wevisone_cells']
        assert reopened.opacity.value() == 31
    finally:
        reopened.close()


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows virtual-environment process tree')
def test_stop_terminates_virtual_environment_child_processes(tmp_path, app):
    import psutil
    window = Window(state_path=tmp_path/'state.json')
    window.process.start(sys.executable, ['-u', '-c', 'import time; print("READY", flush=True); time.sleep(60)'])
    try:
        wait_until(app, lambda: 'READY' in window.log.toPlainText())
        parent = psutil.Process(int(window.process.processId()))
        child_pids = [p.pid for p in parent.children(recursive=True)]
        window.stop()
        wait_until(app, lambda: window.process.state() == QProcess.ProcessState.NotRunning)
        wait_until(app, lambda: not any(psutil.pid_exists(pid) for pid in child_pids))
    finally:
        if window.process.state() != QProcess.ProcessState.NotRunning:
            window.stop(); window.process.waitForFinished(5000)
        window.close()
