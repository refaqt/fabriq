"""File locks through ``git lfs``: who works on which FreeCAD file.

A ``.FCStd`` file is a zip. Git cannot merge two changes to it, so only one
person may change it at a time. Git LFS keeps that promise on the server: a
person takes the lock, and nobody else can push the file until it is
released. Every call here runs ``git lfs`` in one repository, with paths
relative to that repository's root.
"""
from __future__ import annotations

import json
from pathlib import Path

from fabriq.core.git import git

FREECAD_SUFFIX = ".fcstd"


class LockError(RuntimeError):
    """A lock call failed. ``owner`` is set when someone else holds the file."""

    def __init__(self, message: str, owner: str | None = None):
        super().__init__(message)
        self.owner = owner


def is_freecad(path: str) -> bool:
    return path.lower().endswith(FREECAD_SUFFIX)


def lfs_available(path: Path) -> bool:
    try:
        return git(path, "lfs", "version", timeout=15.0).returncode == 0
    except (OSError, ValueError):
        return False


def has_remote(path: Path) -> bool:
    return git(path, "remote", "get-url", "origin", timeout=15.0).returncode == 0


def _entry(raw: dict) -> dict:
    owner = raw.get("owner") or {}
    return {
        "id": str(raw.get("id", "")),
        "path": raw.get("path", ""),
        "owner": owner.get("name", "") if isinstance(owner, dict) else str(owner),
        "locked_at": raw.get("locked_at"),
    }


def _run(path: Path, *args: str, timeout: float = 60.0):
    try:
        return git(path, "lfs", *args, timeout=timeout)
    except (OSError, ValueError) as exc:
        raise LockError(f"git lfs could not run: {exc}") from exc


def verify(path: Path) -> dict:
    """``{"ours": [...], "theirs": [...]}``: the locks on the server, split by owner."""
    result = _run(path, "locks", "--verify", "--json")
    if result.returncode != 0:
        raise LockError(result.stderr.strip() or "git lfs could not list the locks")
    data = json.loads(result.stdout or "{}")
    return {
        "ours": [_entry(e) for e in data.get("ours") or []],
        "theirs": [_entry(e) for e in data.get("theirs") or []],
    }


def owner_of(path: Path, file: str) -> str | None:
    result = _run(path, "locks", "--path", file, "--json")
    if result.returncode != 0:
        return None
    for raw in json.loads(result.stdout or "[]"):
        if raw.get("path") == file:
            return _entry(raw)["owner"] or None
    return None


def lock(path: Path, file: str) -> dict:
    """Take the lock on ``file``. Raises ``LockError`` with the owner when it is taken."""
    result = _run(path, "lock", "--json", file)
    if result.returncode == 0:
        return _entry(json.loads(result.stdout or "{}"))
    message = result.stderr.strip() or result.stdout.strip() or f"could not lock {file}"
    owner = owner_of(path, file)
    raise LockError(message, owner=owner)


def unlock(path: Path, file: str) -> None:
    """Release my lock on ``file``. Never forces: someone else's lock stays."""
    result = _run(path, "unlock", file)
    if result.returncode != 0:
        raise LockError(result.stderr.strip() or result.stdout.strip() or f"could not unlock {file}")


def lockable(path: Path, file: str) -> bool:
    """True when ``.gitattributes`` marks ``file`` as lockable (read-only until locked)."""
    out = git(path, "check-attr", "lockable", "--", file, timeout=15.0).stdout
    return out.strip().endswith(": set")
