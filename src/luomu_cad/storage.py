from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

def project_root() -> Path:
    return Path(os.environ.get('LUOMU_CAD_ROOT', Path(__file__).resolve().parents[2])).resolve()


ROOT = project_root()


def now() -> str:
    # Windows may not have IANA tzdata. A fixed UTC+8 offset is sufficient here.
    from datetime import timedelta, timezone
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                      allow_nan=False, separators=(",", ":")).encode()).hexdigest()


# Windows refuses to replace a file that another process has open, and briefly
# refuses to open a file that is being replaced (sharing violation). A status
# reader polling while a background worker records state hits both. Retry only
# that error, only on Windows, for about one second; anything else still raises.
SHARING_RETRY = os.name == "nt"


def _shared(operation, attempts: int = 50, delay: float = 0.02):
    for attempt in range(attempts):
        try:
            return operation()
        except PermissionError:
            if not SHARING_RETRY or attempt == attempts - 1:
                raise
            time.sleep(delay)


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    _shared(lambda: os.replace(temporary, path))


def inside(path: str | Path, base: Path) -> Path:
    base = base.resolve()
    target = (base / path).resolve()
    if not target.is_relative_to(base):
        raise ValueError(f"Path must stay within {base}")
    return target


def bundle_pending(stage: Path) -> bool:
    return (stage / ".pending.json").is_file()


def recover_bundle(stage: Path) -> None:
    """Roll back an interrupted bundle replacement while holding its workspace lock."""
    if not stage.exists():
        return
    pending = stage / ".pending.json"
    if pending.is_file():
        entries = json.loads(pending.read_text(encoding="utf-8"))
        for index, (source, destination, existed) in reversed(list(enumerate(entries))):
            if inside(source, stage).exists():
                continue  # The staged file was never moved into the drawing bundle.
            target = inside(destination, stage.parent)
            if existed:
                restored = stage / ".restore"
                shutil.copy2(stage / ".backup" / str(index), restored)
                _shared(lambda: os.replace(restored, target))
            else:
                _shared(lambda: target.unlink(missing_ok=True))
        _shared(pending.unlink)
    shutil.rmtree(stage)


@contextmanager
def stage_bundle(stage: Path):
    stage.mkdir()
    try:
        yield
    finally:
        if stage.exists() and not bundle_pending(stage):
            shutil.rmtree(stage)


def publish_bundle(stage: Path, files: list[tuple[Path, Path]]) -> None:
    """Replace a verified file set, keeping its prior state available until commit."""
    backup = stage / ".backup"
    backup.mkdir()
    entries = []
    for index, (source, destination) in enumerate(files):
        existed = destination.exists()
        if existed:
            shutil.copy2(destination, backup / str(index))
        entries.append((str(source.relative_to(stage)), str(destination.relative_to(stage.parent)), existed))
    pending = stage / ".pending.json"
    atomic_json(pending, entries)
    try:
        for source, destination in files:
            _shared(lambda: os.replace(source, destination))
        _shared(pending.unlink)
    except Exception:
        recover_bundle(stage)
        raise


class Journal:
    """Committed jobs replay; unresolved writes never execute a second time."""
    def __init__(self, root: Path):
        self.root = root

    def path(self, job_id: str) -> Path:
        if not job_id or job_id.startswith("_") or len(job_id) > 128 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in job_id):
            raise ValueError("job_id needs 1..128 ASCII letters, numbers, hyphens or underscores")
        return self.root / f"{job_id}.json"

    def get(self, job_id: str):
        path = self.path(job_id)
        return json.loads(_shared(lambda: path.read_text(encoding="utf-8"))) if path.exists() else None

    def begin(self, job_id: str, request: dict) -> tuple[bool, dict]:
        fingerprint = digest(request)
        old = self.get(job_id)
        if old:
            if old["request_hash"] != fingerprint:
                raise ValueError("JOB_CONFLICT: job_id was used with different inputs")
            if old["status"] == "completed":
                return False, old["result"]
            raise ValueError("WRITE_UNCERTAIN: inspect existing job and read back before resuming; automatic replay refused")
        self.set(job_id, {"status": "started", "request_hash": fingerprint, "request": request})
        return True, {}

    def set(self, job_id: str, fields: dict) -> None:
        path = self.path(job_id)
        old = self.get(job_id) or {}
        atomic_json(path, {**old, **fields, "updated": now()})


@contextmanager
def workspace_lock(root: Path):
    """Nonblocking OS file lock, released on process exit, shared by CLI sessions."""
    root.mkdir(parents=True, exist_ok=True)
    with (root / "workspace.lock").open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            raise RuntimeError("WORKSPACE_BUSY: another process owns this output root; no write attempted") from exc
        try:
            yield
        finally:
            if acquired:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
