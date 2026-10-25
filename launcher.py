"""Local Python frontend for the same parameters exposed to Bilayers."""
from pathlib import Path
import json
import subprocess
import sys
from datetime import datetime
import yaml
from PyQt6.QtCore import QProcess, Qt
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (QApplication, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QSpinBox, QTextEdit, QToolButton, QVBoxLayout, QWidget)

ROOT = Path(__file__).resolve().parent
STATE = ROOT / ".last_launcher_settings.json"


def build_local_command(values, input_dir, output_dir, preflight=False):
    command = [sys.executable, "-u", str(ROOT / "wrapper.py"), "--infolder", input_dir, "--outfolder", output_dir]
    for key, value in values.items():
        command += ["--" + key.replace("_", "-"), str(value)]
    if preflight:
        command.append("--preflight-only")
    return command


class CollapsiblePanel(QWidget):
    """Keep advanced descriptor parameters available but initially hidden."""
    def __init__(self, title):
        super().__init__()
        self.toggle = QToolButton(text=title, checkable=True, checked=False)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.content = QWidget()
        self.content.setVisible(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle)
        layout.addWidget(self.content)
        self.toggle.toggled.connect(self.set_open)

    def set_open(self, opened):
        self.content.setVisible(opened)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if opened else Qt.ArrowType.RightArrow)


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setFont(QFont("Segoe UI", 10))
        self.setWindowTitle("CISegWeVisOneVL — 2D microscopy segmentation")
        self.resize(1020, 900)
        self.widgets = {}
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(ROOT))
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(lambda error: self.log.append(self.process.errorString()))
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.addWidget(QLabel("CISegWeVisOneVL • up to four independent 2D segmentation prompts"))
        layout.addWidget(QLabel("English descriptions are recommended. Blank prompts are skipped. Each slot creates its own label group."))
        folders = QFormLayout()
        self.input_path = QLineEdit(str(ROOT / "publicdata" / "ome-zarr"))
        self.output_path = QLineEdit(str(ROOT / "outputfolder"))
        for label, widget in [("Input folder / OME-Zarr", self.input_path), ("Output folder", self.output_path)]:
            row = QWidget()
            horizontal = QHBoxLayout(row)
            horizontal.setContentsMargins(0,0,0,0)
            horizontal.addWidget(widget)
            browse = QPushButton("Browse…")
            browse.clicked.connect(lambda checked=False, target=widget: self.browse(target))
            horizontal.addWidget(browse)
            folders.addRow(label, row)
        layout.addLayout(folders)
        area = QScrollArea(widgetResizable=True)
        form_widget = QWidget()
        parameter_layout = QVBoxLayout(form_widget)
        explanation = QLabel("Each target uses one RGB image: one channel = grayscale; three channels = R,G,B in the entered order. Channels are not inferred separately or automatically combined from all channels.")
        explanation.setWordWrap(True)
        parameter_layout.addWidget(explanation)
        form = QFormLayout()
        parameter_layout.addLayout(form)
        self.advanced_panel = CollapsiblePanel("Advanced parameters")
        advanced_form = QFormLayout(self.advanced_panel.content)
        config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
        for spec in config["parameters"]:
            default = spec.get("default", "")
            kind = spec["type"]
            if spec.get("options"):
                widget = QComboBox()
                for option in spec["options"]:
                    widget.addItem(option["label"], str(option["value"]))
                widget.setCurrentIndex(max(0, widget.findData(str(default))))
                widget.currentIndexChanged.connect(self.preview_command)
            elif kind == "integer":
                widget = QSpinBox()
                widget.setRange(spec.get("minimum", 0), spec.get("maximum", 100000))
                widget.setValue(int(default))
                widget.valueChanged.connect(self.preview_command)
            elif kind == "float":
                widget = QDoubleSpinBox()
                widget.setRange(spec.get("minimum", 0), spec.get("maximum", 1))
                widget.setSingleStep(.05)
                widget.setValue(float(default))
                widget.valueChanged.connect(self.preview_command)
            else:
                widget = QLineEdit(str(default))
                widget.textChanged.connect(self.preview_command)
            widget.setToolTip(spec.get("description", ""))
            self.widgets[spec["name"]] = widget
            target_form = advanced_form if spec.get("mode") == "advanced" else form
            target_form.addRow(spec["label"], widget)
        parameter_layout.addWidget(self.advanced_panel)
        parameter_layout.addStretch()
        area.setWidget(form_widget)
        layout.addWidget(area, 3)
        self.preview = QTextEdit(readOnly=True)
        self.preview.setMaximumHeight(90)
        layout.addWidget(self.preview)
        buttons = QHBoxLayout()
        self.validate_button = QPushButton("Check input")
        self.run_button = QPushButton("Run local Python")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.validate_button.clicked.connect(lambda: self.start(True))
        self.run_button.clicked.connect(lambda: self.start(False))
        self.stop_button.clicked.connect(self.stop)
        for button in [self.validate_button, self.run_button, self.stop_button]:
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.status = QLabel("Ready — local Python, cached model weights, original pixels preserved")
        layout.addWidget(self.status)
        self.example = QComboBox()
        self.example.addItem("Choose a retained public 2D / 3D example…", None)
        try:
            selection_path=ROOT/'gallery_selection.json'
            selected_names={e['name'] for e in json.loads(selection_path.read_text())['examples']} if selection_path.exists() else None
            for item in json.loads((ROOT/"publicdata/catalog.json").read_text()):
                if item.get('show_in_examples') is False:
                    continue
                if selected_names is not None and item['name'] not in selected_names:
                    continue
                self.example.addItem(item["name"], item)
        except (OSError, ValueError):
            pass
        self.example.currentIndexChanged.connect(self.use_example)
        layout.insertWidget(2,self.example)
        self.log = QTextEdit(readOnly=True)
        self.log.document().setMaximumBlockCount(10000)
        layout.addWidget(self.log, 2)
        self.input_path.textChanged.connect(self.preview_command)
        self.output_path.textChanged.connect(self.preview_command)
        self.restore()
        self.preview_command()

    def use_example(self, *_):
        item=self.example.currentData()
        if not item:
            return
        self.input_path.setText(str(ROOT/"publicdata/ome-zarr"/(item["name"]+".ome.zarr")))
        stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
        self.output_path.setText(str(ROOT/"outputfolder"/(item["name"]+"-"+stamp)))
        presets=item.get('prompt_presets') or [{'text':item['suggested_query'],'name':item.get('label_name',"organoids" if item['name'].startswith('organoids') else 'nuclei' if item['name']=='human_mitosis' else 'glands' if item['name']=='immunohistochemistry' else 'cell'),'channels':item['channels']}]
        for slot in range(1,5):
            self.widgets[f'prompt_{slot}'].setText('')
        for slot,preset in enumerate(presets[:4],1):
            self.widgets[f'prompt_{slot}'].setText(preset['text'])
            self.widgets[f'name_{slot}'].setText(preset['name'])
            self.widgets[f'channels_{slot}'].setText(preset.get('channels',item['channels']))
        self.widgets["normalization"].setCurrentIndex(self.widgets["normalization"].findData(item["normalization"]))
        self.status.setText(f"{item.get('kind',item['name'])} • shape {item.get('shape','')} • measurements.csv includes every source channel")

    def browse(self, target):
        path = QFileDialog.getExistingDirectory(self, "Select folder", target.text())
        if path:
            target.setText(path)

    def values(self):
        return {name: widget.currentData() if isinstance(widget, QComboBox) else widget.value() if isinstance(widget, (QSpinBox, QDoubleSpinBox)) else widget.text()
                for name, widget in self.widgets.items()}

    def preview_command(self, *_):
        if hasattr(self, "preview"):
            self.preview.setPlainText(subprocess.list2cmdline(build_local_command(self.values(), self.input_path.text(), self.output_path.text())))

    def restore(self):
        try:
            state = json.loads(STATE.read_text())
        except (OSError, ValueError):
            return
        self.input_path.setText(state.get("input", self.input_path.text()))
        self.output_path.setText(state.get("output", self.output_path.text()))
        for name, value in state.get("values", {}).items():
            widget = self.widgets.get(name)
            if isinstance(widget, QComboBox):
                index = widget.findData(str(value))
                if index >= 0:
                    widget.setCurrentIndex(index)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setValue(value)
            elif isinstance(widget, QLineEdit):
                widget.setText(str(value))

    def start(self, preflight):
        command = build_local_command(self.values(), self.input_path.text(), self.output_path.text(), preflight)
        STATE.write_text(json.dumps({"input": self.input_path.text(), "output": self.output_path.text(), "values": self.values()}, indent=2))
        self.log.clear()
        self.status.setText("Checking input…" if preflight else "Running segmentation…")
        self.run_button.setEnabled(False)
        self.validate_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.process.start(command[0], command[1:])

    def read_output(self):
        content = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self.log.moveCursor(QTextCursor.MoveOperation.End)
        self.log.insertPlainText(content)
        self.log.ensureCursorVisible()

    def finished(self, code, status):
        self.read_output()
        self.status.setText("Completed successfully" if code == 0 else f"Stopped (exit {code}); see log. Partial results are retained.")
        self.run_button.setEnabled(True)
        self.validate_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def stop(self):
        self.process.kill()

    def closeEvent(self, event):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.information(self, "Workflow running", "Stop the running workflow before closing. Partial results will be retained.")
            event.ignore()
        else:
            event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    raise SystemExit(app.exec())
