"""Git LFS locks on FreeCAD files: taken when a file changes, released after the merge.

Real git repositories with a bare remote; a fake ``git-lfs`` on PATH stands
in for the lock server. It keeps the locks in one JSON file, and
``FAKE_LFS_USER`` says who "I" am, so a test can play a colleague.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from fabriq.core import github, lfs
from fabriq.core.changesets import ChangeSet, ChangeSets, RepoChange
from fabriq.core.locks import LockKeeper

GIT = ["-c", "user.name=T", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]
FAKE_LFS = '''
import json, os, sys
from pathlib import Path
store = Path(os.environ["FAKE_LFS_STORE"])
me = os.environ.get("FAKE_LFS_USER", "me")
locks = json.loads(store.read_text()) if store.is_file() else {}
args = [a for a in sys.argv[1:] if a != "--json"]
def entry(path):
    return {"id": str(abs(hash(path)) % 1000), "path": path, "owner": {"name": locks[path]}, "locked_at": "2026-10-07T10:00:00Z"}
if args[:1] == ["version"]:
    print("git-lfs/fake")
elif args[:1] == ["lock"]:
    path = args[1]
    if path in locks:
        print(f"Lock exists: {path}", file=sys.stderr)
        sys.exit(2)
    locks[path] = me
    store.write_text(json.dumps(locks))
    print(json.dumps(entry(path)))
elif args[:1] == ["unlock"]:
    path = args[1]
    if locks.get(path) != me:
        print(f"{path} is locked by {locks.get(path)}", file=sys.stderr)
        sys.exit(2)
    del locks[path]
    store.write_text(json.dumps(locks))
elif args[:2] == ["locks", "--verify"]:
    print(json.dumps({"ours": [entry(p) for p, o in locks.items() if o == me],
                      "theirs": [entry(p) for p, o in locks.items() if o != me]}))
elif args[:2] == ["locks", "--path"]:
    print(json.dumps([entry(args[2])] if args[2] in locks else []))
else:
    sys.exit(3)
'''


def git(path: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(path), *GIT, *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


class Events:
    def __init__(self):
        self.seen: list[dict] = []

    def publish(self, event: dict) -> None:
        self.seen.append(event)


class FakeWorkspace:
    def __init__(self, root: Path):
        self.root = root
        self.libraries = []

    def local_dir(self) -> Path:
        path = self.root / ".fabriq"
        path.mkdir(exist_ok=True)
        return path


@pytest.fixture
def repo(tmp_path: Path, monkeypatch) -> Path:
    if sys.platform == "win32":
        pytest.skip("the fake git-lfs is a shell script")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "fake_lfs.py").write_text(FAKE_LFS, encoding="utf-8")
    script = bin_dir / "git-lfs"
    script.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{bin_dir / "fake_lfs.py"}" "$@"\n', encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("FAKE_LFS_STORE", str(tmp_path / "locks.json"))
    monkeypatch.setenv("FAKE_LFS_USER", "me")
    remote, root = tmp_path / "remote.git", tmp_path / "machine"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "cad").mkdir()
    for name in ("frame.FCStd", "gear.FCStd"):
        (root / "cad" / name).write_bytes(b"zip-1")
    (root / "README.md").write_text("machine\n", encoding="utf-8")
    (root / ".gitignore").write_text(".fabriq/\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "start")
    git(root, "remote", "add", "origin", str(remote))
    git(root, "push", "-q", "-u", "origin", "main")
    return root


def colleague_locks(tmp_path: Path, path: str) -> None:
    store = tmp_path / "locks.json"
    locks = json.loads(store.read_text()) if store.is_file() else {}
    locks[path] = "colleague"
    store.write_text(json.dumps(locks))


def keeper_for(root: Path, events: Events, documents=None) -> LockKeeper:
    return LockKeeper(root / ".fabriq" / "locks.json", events, lambda: [("machine", root, "machine")],
                      documents=documents)


def test_a_changed_freecad_file_is_locked_and_the_lock_goes_with_the_change(repo: Path):
    events = Events()
    keeper = keeper_for(repo, events)
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    (repo / "cad" / "frame.FCStd").write_bytes(b"zip-2")
    status = keeper.sweep()["machine"]
    assert [m["path"] for m in status["mine"]] == ["cad/frame.FCStd"]
    assert status["mine"][0]["reason"] == "saved"
    assert any(e["type"] == "locks.changed" for e in events.seen)
    assert keeper.holds(repo, "cad/frame.FCStd")
    # The lock survives a restart of fabriq.
    assert keeper_for(repo, Events()).holds(repo, "cad/frame.FCStd")
    # Committed but not merged: the lock stays.
    git(repo, "switch", "-q", "-c", "feat/frame")
    git(repo, "commit", "-q", "-am", "frame")
    assert keeper.sweep()["machine"]["mine"]
    # The change is thrown away: the lock goes.
    git(repo, "switch", "-q", "main")
    git(repo, "branch", "-q", "-D", "feat/frame")
    assert keeper.sweep()["machine"]["mine"] == []


def test_unsaved_changes_in_the_open_window_take_the_lock(repo: Path):
    window = [(repo / "cad" / "gear.FCStd", True), (repo / "cad" / "frame.FCStd", False)]
    keeper = keeper_for(repo, Events(), documents=lambda: window)
    mine = keeper.sweep()["machine"]["mine"]
    assert [(m["path"], m["reason"]) for m in mine] == [("cad/gear.FCStd", "unsaved")]
    # The person closes the document without saving: the lock goes.
    window.clear()
    assert keeper.sweep()["machine"]["mine"] == []


def test_a_file_a_colleague_holds_is_not_locked_and_the_person_is_warned(repo: Path, tmp_path: Path):
    colleague_locks(tmp_path, "cad/gear.FCStd")
    events = Events()
    keeper = keeper_for(repo, events)
    (repo / "cad" / "gear.FCStd").write_bytes(b"zip-2")
    status = keeper.sweep()["machine"]
    assert status["mine"] == []
    assert status["conflicts"] == [{"path": "cad/gear.FCStd", "owner": "colleague"}]
    assert status["theirs"][0]["owner"] == "colleague"
    conflicts = [e for e in events.seen if e["type"] == "lock.conflict"]
    assert conflicts and conflicts[0]["owner"] == "colleague"
    # A second pass does not warn again.
    keeper.sweep()
    assert len([e for e in events.seen if e["type"] == "lock.conflict"]) == 1


def test_a_repository_without_a_remote_is_skipped_with_a_warning(repo: Path):
    git(repo, "remote", "remove", "origin")
    keeper = keeper_for(repo, Events())
    (repo / "cad" / "frame.FCStd").write_bytes(b"zip-2")
    status = keeper.sweep()["machine"]
    assert status["mine"] == [] and "no remote" in status["warnings"][0]


def test_a_change_set_keeps_its_locks_until_the_merge(repo: Path, tmp_path: Path, monkeypatch):
    keeper = keeper_for(repo, Events())
    sets = ChangeSets(FakeWorkspace(repo), locks=keeper)
    (repo / "cad" / "frame.FCStd").write_bytes(b"zip-2")
    keeper.sweep()
    cs = ChangeSet(id="cs1", topic="frame", comment="", created=time.time(), repos=[
        RepoChange(name="machine", path=str(repo), kind="machine", branch="feat/frame",
                   files=["cad/frame.FCStd"], commit_message="feat(cad): stiffer frame")])
    cs = sets.commit(cs)
    assert cs.repos[0].locked == ["cad/frame.FCStd"]

    # A colleague holds another file in the change: the push stops before git pushes.
    (repo / "cad" / "gear.FCStd").write_bytes(b"zip-2")
    git(repo, "commit", "-q", "-am", "gear")
    cs.repos[0].files.append("cad/gear.FCStd")
    colleague_locks(tmp_path, "cad/gear.FCStd")
    with pytest.raises(RuntimeError) as err:
        sets.push_and_pr(cs)
    assert "cad/gear.FCStd (colleague)" in str(err.value)

    # The pull request merges: refresh releases the lock.
    cs.repos[0].pr_url = "https://github.example/org/machine/pull/1"
    monkeypatch.setattr(github, "pr_state", lambda path, url: {"state": "MERGED", "merge_commit": "abc"})
    cs = sets.refresh(cs)
    assert cs.repos[0].locked == []
    assert "released the lock on cad/frame.FCStd" in cs.repos[0].notes
    assert not keeper.holds(repo, "cad/frame.FCStd")
    assert lfs.verify(repo)["ours"] == []


def test_a_failed_lock_without_an_owner_is_a_warning_not_a_conflict(repo: Path, monkeypatch):
    events = Events()
    keeper = keeper_for(repo, events)

    def broken(path, file):
        raise lfs.LockError("connection refused")

    monkeypatch.setattr(lfs, "lock", broken)
    (repo / "cad" / "frame.FCStd").write_bytes(b"zip-2")
    status = keeper.sweep()["machine"]
    assert status["mine"] == [] and status["conflicts"] == []
    assert "connection refused" in status["warnings"][0]
    assert not [e for e in events.seen if e["type"] == "lock.conflict"]
