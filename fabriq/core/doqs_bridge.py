"""Reach the workspace's own doqs: import its API, run its commands.

doqs is imported from ``<root>/doqs/scripts`` by putting that folder on
``sys.path``. The scripts import each other by bare name, so this is all they
need. The import surface is ``doqs_api``; its ``API_VERSION`` is checked once.
One process serves one workspace, so one doqs is loaded per process.

``run_doqs`` runs ``python doqs/doqs.py <command> ...`` as a subprocess, so
the result is the one CI gets.
"""
from __future__ import annotations

import importlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

REQUIRED_API = (1, 0)

_loaded: dict[str, ModuleType] = {}


class DoqsError(RuntimeError):
    pass


def load_doqs(scripts: Path) -> ModuleType:
    """The ``doqs_api`` module of this workspace, imported once."""
    key = str(scripts.resolve())
    if key in _loaded:
        return _loaded[key]
    if _loaded:
        # Another workspace was served before (tests do this): drop its modules
        # so the bare-name imports resolve against the new folder.
        other = next(iter(_loaded))
        for name, module in list(sys.modules.items()):
            file = getattr(module, "__file__", None) or ""
            if file.startswith(other):
                del sys.modules[name]
        sys.path[:] = [p for p in sys.path if p != other]
        _loaded.clear()
    if key not in sys.path:
        sys.path.insert(0, key)
    try:
        api = importlib.import_module("doqs_api")
    except ImportError as exc:
        raise DoqsError(
            f"{scripts} has no doqs_api: this doqs is too old for fabriq. Bump the doqs pin "
            f"(git submodule update --remote doqs). Import error: {exc}") from exc
    version = getattr(api, "API_VERSION", (0, 0))
    try:
        api.requires(*REQUIRED_API)
    except RuntimeError as exc:
        raise DoqsError(str(exc)) from exc
    _loaded[key] = api
    api.API_LOADED_FROM = key  # for the workspace page
    api.API_VERSION_FOUND = version
    return api


def doqs_module(scripts: Path, name: str) -> ModuleType:
    """Any doqs script module, after the API was loaded (so the path is set)."""
    load_doqs(scripts)
    return importlib.import_module(name)


@dataclass
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run_doqs(root: Path, args: list[str], timeout: float = 1800.0) -> CommandResult:
    """``python doqs/doqs.py <args>`` in the workspace, captured."""
    cmd = [sys.executable, str(root / "doqs" / "doqs.py"), *args]
    try:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return CommandResult(args, 124, "", f"doqs {' '.join(args)} did not finish in {timeout:.0f} s")
    return CommandResult(args, proc.returncode, proc.stdout, proc.stderr)
