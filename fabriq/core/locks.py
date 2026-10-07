"""The lock keeper: takes the Git LFS lock on a FreeCAD file as soon as it changes.

A FreeCAD file counts as "being changed" when

- the open FreeCAD window has it with unsaved changes (read over the RPC
  port, read only), or
- git sees it as changed on disk.

The keeper then takes the lock, so a colleague cannot change the same file
at the same time. When a colleague already holds it, the keeper does not
lock and tells the browser at once: the person must stop, because the change
cannot be merged.

A lock the keeper took goes away again when the change is gone: the window
has no unsaved changes, the file is clean on disk, and the branch carries no
commit to it that is not on ``origin/main``. A change set releases its locks
itself when its pull request merges or closes.
"""
from __future__ import annotations

import json
import threading
import time
import xmlrpc.client
from pathlib import Path
from typing import Callable

from fabriq.core import lfs
from fabriq.core.events import Broker
from fabriq.core.git import git, repo_status

#: What the keeper sends to the open FreeCAD window. It only reads.
OPEN_DOCUMENTS_CODE = """
import json, FreeCAD
_out = []
for _name, _doc in FreeCAD.listDocuments().items():
    _modified = False
    try:
        import FreeCADGui
        _modified = bool(FreeCADGui.getDocument(_name).Modified)
    except Exception:
        _modified = bool(_doc.isTouched())
    if _doc.FileName:
        _out.append([_doc.FileName, _modified])
print("FABRIQ_DOCS=" + json.dumps(_out))
"""

#: Reasons the keeper sets itself. A lock with another reason (taken by hand,
#: or found on the server) is never released by the keeper.
OWN_REASONS = ("unsaved", "saved")


def open_documents(url: str, timeout: float = 3.0) -> list[tuple[Path, bool]]:
    """``(file, has unsaved changes)`` for each saved document in the open window."""
    import socket

    previous = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        proxy = xmlrpc.client.ServerProxy(url, allow_none=True)
        if not proxy.ping():
            return []
        result = proxy.execute_code(OPEN_DOCUMENTS_CODE)
    except Exception:  # noqa: BLE001 - no window, or no RPC add-on: nothing is open
        return []
    finally:
        socket.setdefaulttimeout(previous)
    text = str(result.get("message", result.get("output", ""))) if isinstance(result, dict) else str(result)
    for line in text.splitlines():
        if line.startswith("FABRIQ_DOCS="):
            try:
                return [(Path(f), bool(m)) for f, m in json.loads(line[len("FABRIQ_DOCS="):])]
            except (ValueError, TypeError):
                return []
    return []


def _repo_of(file: Path) -> Path | None:
    for parent in file.parents:
        if (parent / ".git").exists():
            return parent
    return None


class LockKeeper:
    def __init__(self, store: Path, broker: Broker | None,
                 repositories: Callable[[], list[tuple[str, Path, str]]],
                 documents: Callable[[], list[tuple[Path, bool]]] | None = None,
                 base: str = "origin/main", interval: float = 10.0, verify_every: float = 300.0):
        self.store = store
        self.broker = broker
        self.repositories = repositories
        self.documents = documents or (lambda: [])
        self.base = base
        self.interval = interval
        self.verify_every = verify_every
        self._mutex = threading.RLock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._verified = 0.0
        #: repo path -> file -> {"reason", "since", "id"}
        self.held: dict[str, dict[str, dict]] = {}
        #: repo path -> the colleagues' locks, as the server last said
        self.theirs: dict[str, list[dict]] = {}
        #: (repo path, file) -> owner: files I change that a colleague holds
        self.conflicts: dict[tuple[str, str], str | None] = {}
        self.warnings: dict[str, list[str]] = {}
        self._load()

    # --- persistence ---------------------------------------------------
    def _load(self) -> None:
        if self.store.is_file():
            try:
                self.held = json.loads(self.store.read_text(encoding="utf-8")).get("held", {})
            except (ValueError, OSError):
                self.held = {}

    def _save(self) -> None:
        self.store.parent.mkdir(parents=True, exist_ok=True)
        self.store.write_text(json.dumps({"held": self.held}, indent=1), encoding="utf-8")

    def _publish(self, event: dict) -> None:
        if self.broker is not None:
            self.broker.publish(event)

    # --- the thread ----------------------------------------------------
    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="fabriq-locks", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def poke(self) -> None:
        """Run a pass now, for example after a job changed files."""
        self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.sweep()
            except Exception:  # noqa: BLE001 - the keeper must keep running
                pass
            self._wake.wait(self.interval)
            self._wake.clear()

    # --- one pass ------------------------------------------------------
    def _known(self) -> dict[str, str]:
        return {str(p.resolve()): name for name, p, _ in self.repositories()}

    def changed_files(self) -> dict[str, dict[str, str]]:
        """repo path -> file -> reason, for every FreeCAD file being changed now."""
        found: dict[str, dict[str, str]] = {}
        known = self._known()
        for key in known:
            status = repo_status(Path(key))
            for file in status.get("dirty", []) if status.get("git") else []:
                file = file.split(" -> ")[-1].strip('"')
                if lfs.is_freecad(file):
                    found.setdefault(key, {})[file] = "saved"
        for path, modified in self.documents():
            if not modified or not lfs.is_freecad(path.name):
                continue
            repo = _repo_of(path.resolve())
            if repo is None or str(repo.resolve()) not in known:
                continue
            key = str(repo.resolve())
            rel = path.resolve().relative_to(repo.resolve()).as_posix()
            found.setdefault(key, {})[rel] = "unsaved"
        return found

    def sweep(self) -> dict:
        with self._mutex:
            changed = False
            wanted = self.changed_files()
            if time.monotonic() - self._verified > self.verify_every:
                changed |= self._verify_all()
            seen: set[tuple[str, str]] = set()
            for key, files in wanted.items():
                repo = Path(key)
                if not self._ready(repo):
                    continue
                for file, reason in files.items():
                    seen.add((key, file))
                    if file not in self.held.setdefault(key, {}):
                        changed |= self._take(repo, key, file, reason)
            for pair in [p for p in self.conflicts if p not in seen]:
                del self.conflicts[pair]
                changed = True
            changed |= self._release_finished(wanted)
            if changed:
                self._save()
                self._publish({"type": "locks.changed"})
            return self.status()

    def _ready(self, repo: Path) -> bool:
        key = str(repo.resolve())
        if not lfs.lfs_available(repo):
            self._warn(key, "git-lfs is not installed, so FreeCAD files cannot be locked")
            return False
        if not lfs.has_remote(repo):
            self._warn(key, "this repository has no remote, so there is nowhere to keep a lock")
            return False
        return True

    def _warn(self, key: str, text: str) -> None:
        notes = self.warnings.setdefault(key, [])
        if text not in notes:
            notes.append(text)

    def _take(self, repo: Path, key: str, file: str, reason: str) -> bool:
        try:
            entry = lfs.lock(repo, file)
        except lfs.LockError as exc:
            try:
                ours = {e["path"]: e for e in lfs.verify(repo)["ours"]}
            except lfs.LockError:
                ours = {}
            if file in ours:
                self.held[key][file] = {"reason": reason, "since": time.time(), "id": ours[file]["id"]}
                return True
            if exc.owner is None:
                # No owner: the server or the network failed. Try again on the next pass.
                self._warn(key, f"could not lock {file}: {exc}")
                return False
            pair = (key, file)
            if pair in self.conflicts:
                return False
            self.conflicts[pair] = exc.owner
            self._publish({"type": "lock.conflict", "repo": self._known().get(key, key), "file": file,
                           "owner": exc.owner, "message": str(exc)})
            return True
        self.held[key][file] = {"reason": reason, "since": time.time(), "id": entry.get("id", "")}
        if not lfs.lockable(repo, file):
            self._warn(key, f"{file} is not marked lockable in .gitattributes, so others can still edit it "
                            "by accident; they only see the lock when they push")
        return True

    def _committed_change(self, repo: Path, file: str) -> bool | None:
        """True when the branch has a commit to ``file`` that is not on the base. None: unknown."""
        base = git(repo, "merge-base", "HEAD", self.base)
        if base.returncode != 0:
            return None
        diff = git(repo, "diff", "--quiet", base.stdout.strip(), "HEAD", "--", file)
        return diff.returncode != 0

    def _release_finished(self, wanted: dict[str, dict[str, str]]) -> bool:
        changed = False
        for key, files in list(self.held.items()):
            for file, info in list(files.items()):
                if info.get("reason") not in OWN_REASONS or file in wanted.get(key, {}):
                    continue
                if self._committed_change(Path(key), file) is not False:
                    continue
                try:
                    lfs.unlock(Path(key), file)
                except lfs.LockError:
                    continue
                del files[file]
                changed = True
        return changed

    def _verify_all(self) -> bool:
        """Read the server's view: which locks are mine, which are my colleagues'."""
        self._verified = time.monotonic()
        changed = False
        for key in self._known():
            repo = Path(key)
            if not (lfs.lfs_available(repo) and lfs.has_remote(repo)):
                continue
            try:
                found = lfs.verify(repo)
            except lfs.LockError as exc:
                self._warn(key, f"could not read the locks: {exc}")
                continue
            held = self.held.setdefault(key, {})
            ours = {e["path"]: e for e in found["ours"]}
            for file in [f for f in held if f not in ours]:
                del held[file]
                changed = True
            for file, entry in ours.items():
                if file not in held:
                    held[file] = {"reason": "server", "since": time.time(), "id": entry["id"]}
                    changed = True
            if self.theirs.get(key) != found["theirs"]:
                self.theirs[key] = found["theirs"]
                changed = True
        return changed

    # --- what other parts call -----------------------------------------
    def status(self, fresh: bool = False) -> dict:
        """Per repository: my locks, my colleagues' locks, conflicts and warnings."""
        with self._mutex:
            if fresh:
                if self._verify_all():
                    self._save()
            out = {}
            for key, name in self._known().items():
                out[name] = {
                    "path": key,
                    "mine": [{"path": f, **info} for f, info in sorted(self.held.get(key, {}).items())],
                    "theirs": self.theirs.get(key, []),
                    "conflicts": [{"path": f, "owner": o} for (k, f), o in sorted(self.conflicts.items()) if k == key],
                    "warnings": self.warnings.get(key, []),
                }
            return out

    def holds(self, repo: Path, file: str) -> bool:
        return file in self.held.get(str(repo.resolve()), {})

    def colleague_locks(self, repo: Path, files: list[str]) -> list[dict]:
        """The colleagues' locks, fresh from the server, on any of ``files``."""
        with self._mutex:
            self._verify_all()
            wanted = set(files)
            return [e for e in self.theirs.get(str(repo.resolve()), []) if e["path"] in wanted]

    def release(self, repo: Path, files: list[str]) -> list[str]:
        """Release my locks on ``files``. Returns one note per file."""
        notes = []
        with self._mutex:
            key = str(repo.resolve())
            held = self.held.setdefault(key, {})
            for file in files:
                if file not in held:
                    continue
                try:
                    lfs.unlock(repo, file)
                except lfs.LockError as exc:
                    notes.append(f"could not release the lock on {file}: {exc}")
                    continue
                del held[file]
                notes.append(f"released the lock on {file}")
            self._save()
        self._publish({"type": "locks.changed"})
        return notes
