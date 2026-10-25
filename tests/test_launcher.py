import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QEventLoop, QTimer
from launcher import Window, ROOT, build_local_command


def test_launcher_executes_same_wrapper_and_restores_buttons(tmp_path, monkeypatch):
    import launcher
    monkeypatch.setattr(launcher,"STATE",tmp_path/"launcher-state.json")
    from tools.prepare_publicdata import write_store
    import numpy as np
    source=tmp_path/"source.ome.zarr"
    write_store(source,np.zeros((16,20),np.uint8),"source")
    app=QApplication.instance() or QApplication([])
    window=Window()
    window.input_path.setText(str(source))
    window.output_path.setText(str(tmp_path/"out"))
    window.widgets["prompt_1"].setText("cell")
    window.widgets["name_1"].setText("cell")
    loop=QEventLoop()
    window.process.finished.connect(loop.quit)
    QTimer.singleShot(10000,loop.quit)
    window.start(True)
    loop.exec()
    app.processEvents()
    assert window.process.exitCode()==0,window.log.toPlainText()
    assert window.run_button.isEnabled()
    assert '"valid": true' in window.log.toPlainText()
    window.close()


def test_dataset_presets_fill_prompt_channels_and_clear_unused_slots(tmp_path,monkeypatch):
    import json,shutil,launcher
    shutil.copy2(launcher.ROOT/'config.yaml',tmp_path/'config.yaml')
    (tmp_path/'publicdata').mkdir()
    record={'name':'four-channel-tissue','suggested_query':'bundles','label_name':'bundles','channels':'1,2,3',
            'normalization':'percentile','shape':[1,4,1,12,16],
            'prompt_presets':[{'name':'bundles','text':'vascular bundles','channels':'1,2,3'},
                              {'name':'outer','text':'outer layer','channels':'4'}]}
    hidden={**record,'name':'hidden-em-projection','show_in_examples':False}
    (tmp_path/'publicdata/catalog.json').write_text(json.dumps([record,hidden]))
    monkeypatch.setattr(launcher,'ROOT',tmp_path)
    monkeypatch.setattr(launcher,'STATE',tmp_path/'launcher-state.json')
    app=QApplication.instance() or QApplication([])
    window=Window()
    assert window.example.count()==2  # Placeholder plus the reviewed visible example.
    window.widgets['prompt_4'].setText('old prompt')
    window.example.setCurrentIndex(1)
    assert window.widgets['prompt_1'].text()=='vascular bundles'
    assert window.widgets['channels_2'].text()=='4'
    assert window.widgets['name_2'].text()=='outer'
    assert window.widgets['prompt_4'].text()==''
    window.close()
