"""Replace a completed run only after its images and measurements have succeeded."""
from pathlib import Path
import shutil
from uuid import uuid4

from .io import publish_store


def _child(folder, name):
    folder = Path(folder).resolve()
    path = folder/name
    if Path(name).name != name or name in ('.', '..'):
        raise ValueError('Expected a direct output filename')
    if path.is_symlink() or path.is_junction() or path.resolve().parent != folder:
        raise ValueError(f'Refusing to move a linked path or a path outside the output folder: {path}')
    return path


def replace_completed_run(staging, folder, names):
    folder = Path(folder).resolve()
    staging = Path(staging)
    if _child(folder, staging.name) != staging or not staging.name.startswith('.wevisone-run-'):
        raise ValueError('The completed staging run must be inside the output folder')
    if len(names) != len(set(names)):
        raise ValueError('Repeated output names')
    pairs = [(_child(staging, name), _child(folder, name)) for name in names]
    if any(not source.exists() for source, _ in pairs):
        raise ValueError('The new run is incomplete; existing results have not been changed')
    backup = _child(folder, '.wevisone-previous-'+uuid4().hex+'.partial')
    backup.mkdir()
    old, new = [], []
    try:
        for _, target in pairs:
            if target.exists():
                previous = _child(backup, target.name)
                publish_store(target, previous)
                old.append((previous, target))
        for source, target in pairs:
            publish_store(source, target)
            new.append((target, source))
    except BaseException as exc:
        errors = []
        # Reverse publication before restoring old destinations.
        for source, target in reversed(new):
            try:publish_store(source, target)
            except OSError as rollback_error:errors.append(str(rollback_error))
        for source, target in reversed(old):
            try:publish_store(source, target)
            except OSError as rollback_error:errors.append(str(rollback_error))
        if errors:
            raise RuntimeError(f'Could not publish or fully restore results; previous files remain in {backup}: {errors}') from exc
        try:backup.rmdir()
        except OSError:pass
        raise
    # Resolve the exact backup again before recursive removal on Windows.
    cleanup = _child(folder, backup.name)
    try:
        shutil.rmtree(cleanup)
    except OSError as exc:
        print(f'New results are complete; previous-result cleanup deferred at {cleanup}: {exc}', flush=True)
    try:staging.rmdir()
    except OSError:pass
