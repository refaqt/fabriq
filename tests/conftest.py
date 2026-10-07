"""Test workspaces built from the doqs fixtures.

The doqs checkout comes from ``FABRIQ_TEST_DOQS`` or ``../doqs`` beside this
repository. A test workspace is the doqs ``variant-machine`` fixture with the
doqs scripts copied in at ``doqs/`` and the parts library fixture as the
sibling public and private checkouts.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
DOQS = Path(os.environ.get("FABRIQ_TEST_DOQS") or HERE.parent.parent / "doqs").resolve()


def _copy_doqs(target: Path) -> None:
    (target / "doqs").mkdir(parents=True)
    shutil.copy(DOQS / "doqs.py", target / "doqs" / "doqs.py")
    shutil.copytree(DOQS / "scripts", target / "doqs" / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(DOQS / "templates", target / "doqs" / "templates", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(DOQS / "data", target / "doqs" / "data")


@pytest.fixture(autouse=True)
def git_identity(monkeypatch) -> None:
    """fabriq commits with the person's git identity; a CI runner has none."""
    for kind in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{kind}_NAME", "T")
        monkeypatch.setenv(f"GIT_{kind}_EMAIL", "t@example.com")


@pytest.fixture(scope="session")
def doqs_checkout() -> Path:
    if not (DOQS / "scripts" / "doqs_api.py").is_file():
        pytest.skip(f"no doqs with doqs_api at {DOQS}; set FABRIQ_TEST_DOQS")
    return DOQS


@pytest.fixture
def machine(tmp_path: Path, doqs_checkout: Path) -> Path:
    """A machine repository with the library mounted and sibling checkouts."""
    root = tmp_path / "machine"
    shutil.copytree(doqs_checkout / "tests" / "fixtures" / "variant-machine", root)
    _copy_doqs(root)
    library = doqs_checkout / "tests" / "fixtures" / "parts-library"
    shutil.copytree(library, tmp_path / "stoq")
    shutil.copytree(library, tmp_path / "stoq-private")
    (tmp_path / "stoq-private" / "library.toml").write_text(
        'schema = "doqs-library-v1"\nname = "stoq"\nprivate = true\n', encoding="utf-8")
    return root


@pytest.fixture
def stub_env(doqs_checkout: Path, tmp_path: Path, monkeypatch) -> Path:
    """Point FreeCAD jobs at the doqs fake FreeCAD, driven by this Python."""
    stub = doqs_checkout / "tests" / "freecad_stub"
    log = tmp_path / "journal.jsonl"
    monkeypatch.setenv("PYTHONPATH", str(stub))
    monkeypatch.setenv("DOQS_FREECAD_STUB_LOG", str(log))
    monkeypatch.setenv("FABRIQ_FREECAD", sys.executable)
    monkeypatch.setenv("FABRIQ_FREECAD_MODE", "cmd")
    return log
