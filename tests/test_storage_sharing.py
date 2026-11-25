"""Job journal survives Windows sharing violations between a status reader and a worker."""
from pathlib import Path

import pytest

from luomu_cad import storage


def _flaky(real, failures, name):
    calls = {'failed': 0}

    def wrapper(*args, **kwargs):
        target = Path(args[-1] if real.__name__ == 'replace' else args[0])
        if target.name == name and calls['failed'] < failures:
            calls['failed'] += 1
            raise PermissionError(13, 'The process cannot access the file because it is being used')
        return real(*args, **kwargs)
    return wrapper, calls


def test_reader_and_atomic_writer_retry_windows_sharing_violations(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'SHARING_RETRY', True)
    monkeypatch.setattr(storage.time, 'sleep', lambda _: None)
    journal = storage.Journal(tmp_path)
    journal.set('one', {'status': 'queued'})

    read, read_calls = _flaky(Path.read_text, 3, 'one.json')
    monkeypatch.setattr(Path, 'read_text', read)
    assert journal.get('one')['status'] == 'queued' and read_calls['failed'] == 3

    replace, replace_calls = _flaky(storage.os.replace, 3, 'one.json')
    monkeypatch.setattr(storage.os, 'replace', replace)
    journal.set('one', {'status': 'running'})
    assert replace_calls['failed'] == 3
    monkeypatch.undo()
    assert storage.Journal(tmp_path).get('one')['status'] == 'running'


def test_sharing_violations_are_not_hidden_off_windows_or_when_persistent(tmp_path, monkeypatch):
    monkeypatch.setattr(storage.time, 'sleep', lambda _: None)
    journal = storage.Journal(tmp_path)
    journal.set('one', {'status': 'queued'})
    read, _ = _flaky(Path.read_text, 1, 'one.json')
    monkeypatch.setattr(Path, 'read_text', read)
    monkeypatch.setattr(storage, 'SHARING_RETRY', False)
    with pytest.raises(PermissionError):
        journal.get('one')
    monkeypatch.setattr(storage, 'SHARING_RETRY', True)
    always, _ = _flaky(Path.read_text, 10 ** 6, 'one.json')
    monkeypatch.setattr(Path, 'read_text', always)
    with pytest.raises(PermissionError):
        journal.get('one')
