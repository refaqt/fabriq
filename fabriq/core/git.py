"""Git as fabriq sees it: status per repository, branches, commits, pushes.

Every call runs the ``git`` binary. Nothing here decides what to commit;
that comes from the doqs reports through the change-set layer.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def git(path: Path, *args: str, timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, timeout=timeout)


def repo_status(path: Path) -> dict:
    """Branch, dirty files, submodule pins and whether the repo is ahead of its remote."""
    if not (path / ".git").exists():
        return {"path": str(path), "git": False}
    branch = git(path, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    head = git(path, "rev-parse", "--short", "HEAD").stdout.strip()
    porcelain = git(path, "status", "--porcelain").stdout.splitlines()
    dirty = [line[3:].strip() for line in porcelain if line.strip()]
    pins = []
    for line in git(path, "submodule", "status").stdout.splitlines():
        if not line.strip():
            continue
        mark = line[0] if line[0] in "+-U" else " "
        rest = line[1:].split()
        if len(rest) >= 2:
            pins.append({"path": rest[1], "commit": rest[0][:10],
                         "state": {"+": "moved", "-": "missing", "U": "conflict"}.get(mark, "pinned")})
    upstream = git(path, "rev-parse", "--abbrev-ref", "@{upstream}")
    ahead = behind = None
    if upstream.returncode == 0:
        counts = git(path, "rev-list", "--left-right", "--count", "HEAD...@{upstream}").stdout.split()
        if len(counts) == 2:
            ahead, behind = int(counts[0]), int(counts[1])
    return {
        "path": str(path), "git": True, "branch": branch, "head": head, "dirty": dirty,
        "pins": pins, "ahead": ahead, "behind": behind,
        "upstream": upstream.stdout.strip() if upstream.returncode == 0 else None,
    }


def create_branch(path: Path, name: str, base: str = "origin/main") -> str:
    """Create or switch to ``name`` from ``base`` (fetched first when remote)."""
    if base.startswith("origin/"):
        git(path, "fetch", "-q", "origin")
    exists = git(path, "rev-parse", "--verify", "-q", name).returncode == 0
    result = git(path, "switch", "-q", name) if exists else git(path, "switch", "-q", "-c", name, base)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"could not switch to {name}")
    return name


def commit(path: Path, paths: list[str], message: str, force_paths: tuple[str, ...] = ("doqs", ".agents")) -> str | None:
    """Stage ``paths`` and commit. Returns the commit sha, or None when nothing changed."""
    normal = [p for p in paths if p not in force_paths]
    forced = [p for p in paths if p in force_paths]
    if normal:
        git(path, "add", "--", *normal)
    if forced:
        git(path, "add", "--force", "--", *forced)
    if not git(path, "diff", "--cached", "--quiet").returncode:
        return None
    result = subprocess.run(["git", "-C", str(path), "commit", "-q", "-F", "-"],
                            input=message, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "commit failed")
    return git(path, "rev-parse", "HEAD").stdout.strip()


def push(path: Path, branch: str) -> None:
    result = git(path, "push", "-q", "-u", "origin", branch, timeout=600.0)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "push failed")
