from pathlib import Path

import pytest

from ciseg_wevisonevl.io import publish_store


def windows_lock():
    error = PermissionError('Temporary Windows sharing lock')
    error.winerror = 32
    return error


def test_publish_retries_temporary_windows_lock(tmp_path, monkeypatch):
    partial, output = tmp_path/'partial', tmp_path/'complete'
    partial.mkdir()
    (partial/'pixels').write_bytes(b'original pixels')
    rename = Path.rename
    calls = []
    delays = []
    def locked_once(self, target):
        calls.append(target)
        if len(calls) == 1:
            raise windows_lock()
        return rename(self, target)
    monkeypatch.setattr(Path, 'rename', locked_once)
    monkeypatch.setattr('ciseg_wevisonevl.io.time.sleep', delays.append)
    publish_store(partial, output)
    assert len(calls) == 2 and delays == [.05]
    assert not partial.exists()
    assert (output/'pixels').read_bytes() == b'original pixels'


def test_persistent_lock_is_bounded_and_preserves_partial(tmp_path, monkeypatch):
    partial, output = tmp_path/'partial', tmp_path/'complete'
    partial.mkdir()
    calls = []
    def locked(self, target):
        calls.append(target)
        raise windows_lock()
    monkeypatch.setattr(Path, 'rename', locked)
    monkeypatch.setattr('ciseg_wevisonevl.io.time.sleep', lambda delay: None)
    with pytest.raises(PermissionError):
        publish_store(partial, output)
    assert len(calls) == 8
    assert partial.exists() and not output.exists()


def test_retry_never_overwrites_destination_created_during_wait(tmp_path, monkeypatch):
    partial, output = tmp_path/'partial', tmp_path/'complete'
    partial.mkdir()
    def locked(self, target):
        raise windows_lock()
    def another_writer(delay):
        output.mkdir()
        (output/'existing').write_bytes(b'keep')
    monkeypatch.setattr(Path, 'rename', locked)
    monkeypatch.setattr('ciseg_wevisonevl.io.time.sleep', another_writer)
    with pytest.raises(FileExistsError):
        publish_store(partial, output)
    assert partial.exists() and (output/'existing').read_bytes() == b'keep'


def test_unrelated_errors_are_not_retried(tmp_path, monkeypatch):
    partial, output = tmp_path/'partial', tmp_path/'complete'
    partial.mkdir()
    def denied(self, target):
        raise PermissionError('Permanent non-Windows failure')
    def unexpected_wait(delay):
        pytest.fail('Unexpected retry')
    monkeypatch.setattr(Path, 'rename', denied)
    monkeypatch.setattr('ciseg_wevisonevl.io.time.sleep', unexpected_wait)
    with pytest.raises(PermissionError, match='Permanent'):
        publish_store(partial, output)
    assert partial.exists() and not output.exists()
