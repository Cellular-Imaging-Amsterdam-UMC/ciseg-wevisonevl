"""Local segmentation GUI with parameters on the left and one image/label viewer."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, QProcess, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPalette, QPixmap
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDockWidget,
    QColorDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QSizePolicy, QSlider, QSpinBox, QSplitter, QVBoxLayout, QWidget)

from launcher import Window as LauncherWindow
from ciseg_wevisonevl.io import discover, inspect_store
from gui.image_data import load_frame
from gui.viewer import ImageViewer


class LoadSignals(QObject):
    complete = pyqtSignal(int, object, object)


class LoadFrame(QRunnable):
    def __init__(self, generation, args, is_current):
        super().__init__()
        self.generation, self.args = generation, args
        self.is_current = is_current
        self.signals = LoadSignals()

    def run(self):
        if not self.is_current():
            self.signals.complete.emit(self.generation, None, None)
            return
        try:
            payload, error = load_frame(*self.args), None
        except Exception as exc:
            payload, error = None, str(exc)
        self.signals.complete.emit(self.generation, payload, error)


class Window(LauncherWindow):
    def __init__(self, *, state_path=None):
        super().__init__(state_path=state_path or ROOT/'.last_gui_settings.json')
        self.setWindowTitle('CISegWeVisOneVL — image and label viewer')
        self.resize(1520, 980)
        self.fields = []
        self.generation = 0
        self.workers = {}
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.loading_stores = False
        self.running_output = None
        self.preflight_run = True
        self.layer_checks = {}
        self.selected_store = None
        sidebar = self.takeCentralWidget()
        sidebar.setMinimumWidth(370)
        sidebar.setMaximumWidth(640)
        side_layout = sidebar.layout()
        side_layout.itemAt(0).widget().setText('Segmentation parameters')
        side_layout.itemAt(1).widget().setText('Choose an image and describe up to four targets. Blank prompts are skipped.')
        for label in sidebar.findChildren(QLabel):
            label.setWordWrap(True)
        for combo in sidebar.findChildren(QComboBox):
            combo.setMinimumContentsLength(10)
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for form in sidebar.findChildren(QFormLayout):
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.preview.hide()
        side_layout.removeWidget(self.log)
        side_layout.removeWidget(self.status)
        self.status.setMinimumWidth(0)
        self.statusBar().addWidget(self.status, 1)
        self.log_dock = QDockWidget('Run log', self)
        self.log_dock.setWidget(self.log)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.log_dock.hide()

        panel = QWidget()
        layout = QVBoxLayout(panel)
        toolbar = QHBoxLayout()
        for text, callback in [('Load input', self.load_input), ('Open results…', self.open_results)]:
            button = QPushButton(text); button.clicked.connect(callback); toolbar.addWidget(button)
        toolbar.addStretch()
        fit = QPushButton('Fit'); fit.clicked.connect(lambda: self.viewer.fit_image()); toolbar.addWidget(fit)
        actual = QPushButton('1:1'); actual.clicked.connect(lambda: self.viewer.actual_size()); toolbar.addWidget(actual)
        log = QPushButton('Log'); log.clicked.connect(lambda: self.log_dock.setVisible(not self.log_dock.isVisible())); toolbar.addWidget(log)
        layout.addLayout(toolbar)
        selectors = QHBoxLayout()
        self.store_combo = QComboBox(); self.store_combo.setMinimumContentsLength(18)
        self.store_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.store_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.field_combo = QComboBox()
        self.time_spin = QSpinBox(); self.time_spin.setRange(1, 1)
        for title, widget in [('Image', self.store_combo), ('Field', self.field_combo), ('T', self.time_spin)]:
            selectors.addWidget(QLabel(title)); selectors.addWidget(widget)
        layout.addLayout(selectors)
        view_options = QHBoxLayout()
        self.background_channels = QComboBox()
        self.background_channels.setMinimumContentsLength(16)
        self.background_channels.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.background_channels.setToolTip('Choose the channels of the image behind the labels. Prompts with the same channel map share one background. Label visibility is controlled in the list below.')
        self.view_mode = QComboBox()
        self.view_mode.addItems(['Projection (run setting)', 'Z section'])
        self.z_spin = QSpinBox(); self.z_spin.setRange(1, 1); self.z_spin.setEnabled(False)
        self.show_labels = QCheckBox('Show labels'); self.show_labels.setChecked(True)
        self.opacity = QSlider(Qt.Orientation.Horizontal); self.opacity.setRange(0, 100); self.opacity.setValue(45); self.opacity.setMaximumWidth(150)
        for widget in (QLabel('Background:'), self.background_channels, self.view_mode, QLabel('Z'), self.z_spin, self.show_labels, QLabel('Opacity'), self.opacity):view_options.addWidget(widget)
        view_options.addStretch()
        layout.addLayout(view_options)
        self.image_title = QLabel('Open an OME-Zarr image or choose a reviewed example.')
        self.image_title.setWordWrap(True)
        layout.addWidget(self.image_title)
        self.viewer = ImageViewer(); layout.addWidget(self.viewer, 1)
        self.layer_list = QListWidget(); self.layer_list.setMaximumHeight(125)
        self.layer_list.setToolTip('Independent prompt layers may overlap. Uncheck a layer to hide it. Hover over the image for instance IDs.')
        layout.addWidget(self.layer_list)
        color_controls = QHBoxLayout()
        color_controls.addWidget(QLabel('Selected label:'))
        self.selected_label_name = QLabel('No label selected')
        color_controls.addWidget(self.selected_label_name)
        self.label_color_mode = QComboBox()
        self.label_color_mode.addItem('Single color for this prompt', 'single')
        self.label_color_mode.addItem('Different colors per object', 'instances')
        self.label_color_mode.setEnabled(False)
        self.label_color_button = QPushButton('Choose color…')
        self.label_color_button.setEnabled(False)
        self.label_color_button.setToolTip('Choose one color for all objects of the selected prompt. Per-object mode uses stable instance colors.')
        color_controls.addWidget(self.label_color_mode)
        color_controls.addWidget(self.label_color_button)
        color_controls.addStretch()
        layout.addLayout(color_controls)
        self.view_status = QLabel('Mouse wheel: zoom · drag: pan · Fit: show the whole image')
        self.view_status.setWordWrap(True); layout.addWidget(self.view_status)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(sidebar); splitter.addWidget(panel)
        splitter.setStretchFactor(1, 1); splitter.setSizes([460, 1060])
        self.setCentralWidget(splitter)

        self.refresh_timer = QTimer(self); self.refresh_timer.setSingleShot(True); self.refresh_timer.setInterval(180)
        self.refresh_timer.timeout.connect(self.refresh_frame)
        self.store_combo.currentIndexChanged.connect(self.select_store)
        self.field_combo.currentIndexChanged.connect(self.select_field)
        self.time_spin.valueChanged.connect(self.schedule_refresh)
        self.background_channels.currentIndexChanged.connect(self.schedule_refresh)
        self.view_mode.currentIndexChanged.connect(self.change_view_mode)
        self.z_spin.valueChanged.connect(self.schedule_refresh)
        self.opacity.valueChanged.connect(self.viewer.set_opacity)
        self.show_labels.toggled.connect(self.toggle_labels)
        self.layer_list.itemChanged.connect(self.change_layer)
        self.layer_list.currentRowChanged.connect(self.select_label)
        self.label_color_mode.currentIndexChanged.connect(self.change_label_color_mode)
        self.label_color_button.clicked.connect(self.choose_label_color)
        self.viewer.pixel_hovered.connect(self.pixel_hovered)
        for name in ['normalization', 'projection']:
            self.widgets[name].currentIndexChanged.connect(self.schedule_refresh)
        for slot in range(1, 5):
            self.widgets[f'channels_{slot}'].textChanged.connect(self.update_background_choices)
            self.widgets[f'prompt_{slot}'].textChanged.connect(self.update_background_choices)
        self.process.errorOccurred.connect(self.process_error)
        self.update_background_choices()
        self.restore_view_settings()
        QTimer.singleShot(0, self.load_input)

    def update_background_choices(self, *_):
        previous = self.background_channels.currentData()
        slots = [slot for slot in range(1, 5) if self.widgets[f'prompt_{slot}'].text().strip()] or [1]
        choices = {}
        for slot in slots:
            raw = self.widgets[f'channels_{slot}'].text()
            try:
                channels = tuple(int(c.strip()) for c in raw.split(','))
            except ValueError:
                continue
            if len(channels) not in (1, 3) or min(channels) < 1:continue
            choices.setdefault(channels, []).append(slot)
        self.background_channels.blockSignals(True)
        self.background_channels.clear()
        for channels, slots in choices.items():
            label = f'Grayscale: channel {channels[0]}' if len(channels) == 1 else 'RGB: '+','.join(map(str, channels))
            self.background_channels.addItem(label, channels)
            index = self.background_channels.count()-1
            self.background_channels.setItemData(index, 'Background used by prompt '+', '.join(map(str, slots))+'. All enabled label layers remain visible.', Qt.ItemDataRole.ToolTipRole)
        index = next((i for i in range(self.background_channels.count()) if self.background_channels.itemData(i) == previous), 0)
        self.background_channels.setCurrentIndex(index)
        self.background_channels.setEnabled(len(choices) > 1)
        self.background_channels.blockSignals(False)
        self.schedule_refresh()

    def browse(self, target):
        super().browse(target)
        if target is self.input_path:
            self.load_input()

    def use_example(self, *args):
        super().use_example(*args)
        if hasattr(self, 'store_combo') and self.example.currentData():self.load_input()

    def load_input(self):
        self.load_stores(self.input_path.text())

    def load_stores(self, path):
        try:
            stores = discover(path)
        except Exception as exc:
            self.view_status.setText(str(exc)); return
        self.generation += 1
        self.loading_stores = True
        self.store_combo.clear()
        for store in stores:self.store_combo.addItem(store.name, str(store))
        self.loading_stores = False
        self.viewer.auto_fit = True
        self.select_store()

    def open_results(self):
        path = QFileDialog.getExistingDirectory(self, 'Open completed output folder or OME-Zarr', self.output_path.text())
        if path:self.load_stores(path)

    def select_store(self, *_):
        if self.loading_stores:return
        self.generation += 1
        path = self.store_combo.currentData()
        if not path:return
        self.viewer.clear_frame(); self.layer_list.clear()
        try:
            self.fields = inspect_store(Path(path), [])
        except Exception as exc:
            self.fields = []; self.view_status.setText(str(exc)); return
        self.selected_store = Path(path)
        self.field_combo.blockSignals(True); self.field_combo.clear()
        for field in self.fields:self.field_combo.addItem(field.path or 'Image', field.path)
        self.field_combo.blockSignals(False)
        self.select_field()

    def select_field(self, *_):
        index = self.field_combo.currentIndex()
        if not 0 <= index < len(self.fields):return
        field = self.fields[index]
        self.generation += 1
        self.time_spin.setRange(1, field.timepoints)
        self.z_spin.setRange(1, field.z_planes)
        self.schedule_refresh()

    def change_view_mode(self):
        self.z_spin.setEnabled(self.view_mode.currentIndex() == 1)
        self.schedule_refresh()

    def schedule_refresh(self, *_):
        self.generation += 1
        if hasattr(self, 'refresh_timer'):self.refresh_timer.start()

    def refresh_frame(self):
        index = self.field_combo.currentIndex()
        if not 0 <= index < len(self.fields):return
        channels = self.background_channels.currentData()
        if channels is None:
            self.viewer.clear_frame(); self.layer_list.clear()
            self.view_status.setText('Enter one channel or three comma-separated RGB channels.'); return
        self.generation += 1
        worker = LoadFrame(self.generation, (self.fields[index], self.time_spin.value()-1, channels,
            self.widgets['normalization'].currentData(), self.widgets['projection'].currentData(),
            self.z_spin.value()-1 if self.view_mode.currentIndex() == 1 else None),
            lambda token=self.generation: token == self.generation)
        # Keep signal owners alive until their queued result has been received.
        self.workers[self.generation] = worker
        worker.signals.complete.connect(self.frame_loaded)
        self.view_status.setText('Loading image and labels…')
        self.pool.start(worker)

    def frame_loaded(self, generation, frame, error):
        self.workers.pop(generation, None)
        if generation != self.generation:return
        if error:
            self.viewer.clear_frame(); self.layer_list.clear()
            self.image_title.setText(f'{self.selected_store.name if self.selected_store else "Image"} · view unavailable')
            self.view_status.setText(error); return
        self.viewer.set_frame(frame['rgb'], frame['labels'])
        previous = self.layer_list.currentItem()
        selected_name = previous.data(Qt.ItemDataRole.UserRole) if previous else None
        self.layer_list.blockSignals(True); self.layer_list.clear()
        for name, plane in frame['labels'].items():
            count = len(np.unique(plane[plane > 0]))
            item = QListWidgetItem(f'{name.removeprefix("wevisone_")} · {count} '+('object' if count == 1 else 'objects'))
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if self.layer_checks.get(name, True) else Qt.CheckState.Unchecked)
            self.layer_list.addItem(item)
            self.update_label_icon(item)
            self.viewer.layers[name].setVisible(self.show_labels.isChecked() and self.layer_checks.get(name, True))
        selected_index = next((i for i in range(self.layer_list.count()) if self.layer_list.item(i).data(Qt.ItemDataRole.UserRole) == selected_name), 0)
        if self.layer_list.count():self.layer_list.setCurrentRow(selected_index)
        self.layer_list.blockSignals(False)
        self.select_label()
        self.image_title.setText(frame['title']+' · '+frame['view'])
        ranges = ' · '.join(f"C{r['channel']}: {r['low']:g}–{r['high']:g}" for r in frame['limits'])
        self.view_status.setText(ranges + (' · '+'; '.join(frame['notes']) if frame['notes'] else ' · '+str(len(frame['labels']))+' label layers')
                                + (' · Saved labels; run again to apply changed prompts.' if frame['labels'] else ''))

    def update_label_icon(self, item):
        style = self.viewer.layer_style(item.data(Qt.ItemDataRole.UserRole))
        icon = QPixmap(16, 16)
        icon.fill(QColor(style['color']))
        if style['mode'] == 'instances':
            painter = QPainter(icon)
            for index, color in enumerate(('#ff5a9d', '#00c8ff', '#ffb84d', '#b28dff')):
                painter.fillRect((index % 2)*8, (index // 2)*8, 8, 8, QColor(color))
            painter.end()
        item.setIcon(QIcon(icon))
        item.setToolTip('Single color for this prompt' if style['mode'] == 'single' else 'Different colors per object in this prompt')

    def select_label(self, *_):
        item = self.layer_list.currentItem()
        self.label_color_mode.setEnabled(item is not None)
        self.label_color_button.setEnabled(item is not None)
        if item is None:
            self.selected_label_name.setText('No label selected')
            self.label_color_button.setStyleSheet('')
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        style = self.viewer.layer_style(name)
        self.selected_label_name.setText(name.removeprefix('wevisone_'))
        self.label_color_mode.blockSignals(True)
        self.label_color_mode.setCurrentIndex(self.label_color_mode.findData(style['mode']))
        self.label_color_mode.blockSignals(False)
        self.label_color_button.setEnabled(style['mode'] == 'single')
        color = QColor(style['color'])
        text_color = '#111111' if color.lightness() > 140 else '#ffffff'
        self.label_color_button.setStyleSheet(f'background-color: {color.name()}; color: {text_color};')

    def change_label_color_mode(self):
        item = self.layer_list.currentItem()
        if item is None:return
        name = item.data(Qt.ItemDataRole.UserRole)
        self.viewer.set_layer_style(name, mode=self.label_color_mode.currentData())
        for index in range(self.layer_list.count()):self.update_label_icon(self.layer_list.item(index))
        self.select_label()

    def choose_label_color(self):
        item = self.layer_list.currentItem()
        if item is None:return
        name = item.data(Qt.ItemDataRole.UserRole)
        chosen = QColorDialog.getColor(QColor(self.viewer.layer_style(name)['color']), self, 'Choose prompt label color')
        if chosen.isValid():
            self.viewer.set_layer_style(name, color=chosen.name())
            for index in range(self.layer_list.count()):self.update_label_icon(self.layer_list.item(index))
            self.select_label()

    def restore_view_settings(self):
        try:
            state = json.loads(self.state_path.read_text(encoding='utf-8')).get('viewer', {})
        except (OSError, ValueError):
            return
        if not isinstance(state, dict):return
        styles = state.get('label_styles', {})
        if isinstance(styles, dict):
            for name, style in styles.items():
                if not isinstance(name, str) or not isinstance(style, dict):continue
                try:self.viewer.set_layer_style(name, mode=style.get('mode', 'single'), color=style.get('color', '#ff5a9d'))
                except (TypeError, ValueError):continue
        visibility = state.get('label_visibility', {})
        if isinstance(visibility, dict):self.layer_checks = {name: visible for name, visible in visibility.items() if isinstance(name, str) and isinstance(visible, bool)}
        if isinstance(state.get('show_labels'), bool):self.show_labels.setChecked(state['show_labels'])
        if isinstance(state.get('opacity'), int):self.opacity.setValue(state['opacity'])

    def save_view_settings(self):
        try:
            state = json.loads(self.state_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            state = {}
        if not isinstance(state, dict):state = {}
        state['viewer'] = {'label_styles': self.viewer.layer_styles, 'label_visibility': self.layer_checks,
                           'show_labels': self.show_labels.isChecked(), 'opacity': self.opacity.value()}
        temporary = self.state_path.with_name(self.state_path.name+'.partial')
        temporary.write_text(json.dumps(state, indent=2), encoding='utf-8')
        temporary.replace(self.state_path)

    def toggle_labels(self, visible):
        self.viewer.labels_visible = visible
        for name, item in self.viewer.layers.items():item.setVisible(visible and self.layer_checks.get(name, True))

    def change_layer(self, item):
        name = item.data(Qt.ItemDataRole.UserRole)
        self.layer_checks[name] = item.checkState() == Qt.CheckState.Checked
        if name in self.viewer.layers:self.viewer.layers[name].setVisible(self.show_labels.isChecked() and self.layer_checks[name])

    def pixel_hovered(self, x, y):
        pixmap = self.viewer.image_item.pixmap()
        if not 0 <= x < pixmap.width() or not 0 <= y < pixmap.height():return
        ids = [f'{name.removeprefix("wevisone_")}: {plane[y,x]}' for name, plane in self.viewer.label_arrays.items() if plane[y,x] > 0 and self.layer_checks.get(name, True) and self.show_labels.isChecked()]
        self.status.setText(f'X {x}, Y {y}' + (' · '+' · '.join(ids) if ids else ' · background'))

    def start(self, preflight):
        self.preflight_run = preflight
        self.running_output = Path(self.output_path.text()).resolve()
        self.log_dock.show()
        super().start(preflight)

    def finished(self, code, status):
        super().finished(code, status)
        if code == 0 and not self.preflight_run and self.running_output:
            self.view_mode.setCurrentIndex(0)
            self.load_stores(self.running_output)

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:self.finished(-1, QProcess.ExitStatus.CrashExit)

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted():
            self.refresh_timer.stop(); self.pool.clear(); self.pool.waitForDone()
            self.save_view_settings()


def apply_theme(app):
    # Qt's offscreen platform does not discover Windows system fonts itself.
    if sys.platform == 'win32' and not QFontDatabase.families():
        QFontDatabase.addApplicationFont(str(Path('C:/Windows/Fonts/segoeui.ttf')))
    app.setFont(QFont('Segoe UI', 10))
    app.setStyle('Fusion')
    palette = QPalette()
    for role, color in [(QPalette.ColorRole.Window, '#222222'), (QPalette.ColorRole.WindowText, '#eeeeee'),
                        (QPalette.ColorRole.Base, '#181818'), (QPalette.ColorRole.AlternateBase, '#2c2c2c'),
                        (QPalette.ColorRole.Text, '#eeeeee'), (QPalette.ColorRole.Button, '#303030'),
                        (QPalette.ColorRole.ButtonText, '#eeeeee'), (QPalette.ColorRole.Highlight, '#317d63'),
                        (QPalette.ColorRole.HighlightedText, '#ffffff')]:
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor('#888888'))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor('#888888'))
    app.setPalette(palette)


def main():
    app = QApplication(sys.argv)
    apply_theme(app)
    window = Window()
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
