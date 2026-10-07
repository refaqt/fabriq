"""The workspace: one machine repository (or one library) and what it reaches.

``find_root`` walks up from a folder until it finds a machine root (an
``okh.toml`` next to ``doqs/scripts/cli.py``) or a library root
(``library.toml``). The rule is the same one the doqs build seed uses to find
``doqs/scripts``.

A machine mounts its libraries as submodules under ``modules/``; those are
read-only here. Writes go to sibling checkouts (``../stoq``,
``../stoq-private`` by default), named in ``.fabriq/local.toml``.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from fabriq.config import Settings


class WorkspaceError(RuntimeError):
    pass


@dataclass
class LibraryCheckout:
    name: str
    mounted: Path | None       # inside the machine, read-only
    public: Path | None        # a checkout beside the machine
    private: Path | None       # the private checkout beside the machine

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "mounted": str(self.mounted) if self.mounted else None,
            "public": str(self.public) if self.public and self.public.is_dir() else None,
            "private": str(self.private) if self.private and self.private.is_dir() else None,
        }


@dataclass
class Workspace:
    root: Path
    kind: str                  # "machine" | "library"
    doqs_scripts: Path
    settings: Settings
    libraries: list[LibraryCheckout] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.root.name

    def local_dir(self) -> Path:
        path = self.root / ".fabriq"
        path.mkdir(exist_ok=True)
        return path

    def as_dict(self) -> dict:
        return {
            "root": str(self.root),
            "name": self.name,
            "kind": self.kind,
            "doqs_scripts": str(self.doqs_scripts),
            "libraries": [lib.as_dict() for lib in self.libraries],
        }


def is_machine_root(path: Path) -> bool:
    return (path / "okh.toml").is_file() and (path / "doqs" / "scripts" / "cli.py").is_file()


def is_library_root(path: Path) -> bool:
    return (path / "library.toml").is_file()


def find_root(start: Path) -> Path:
    """The nearest workspace root at or above ``start``."""
    start = start.resolve()
    for base in [start, *start.parents]:
        if is_machine_root(base) or (is_library_root(base) and (base / "doqs" / "scripts" / "cli.py").is_file()):
            return base
    raise WorkspaceError(
        f"no workspace at or above {start}: a machine root has okh.toml beside doqs/scripts/cli.py; "
        "a library root has library.toml. Pass --root, or run setup-tooling.sh in the repository first."
    )


def _library_name(path: Path) -> str:
    marker = path / "library.toml"
    try:
        return str(tomllib.loads(marker.read_text(encoding="utf-8")).get("name", path.name))
    except (OSError, tomllib.TOMLDecodeError):
        return path.name


def _is_private(path: Path) -> bool:
    marker = path / "library.toml"
    try:
        return tomllib.loads(marker.read_text(encoding="utf-8")).get("private") is True
    except (OSError, tomllib.TOMLDecodeError):
        return False


def discover_libraries(root: Path, settings: Settings) -> list[LibraryCheckout]:
    """Mounted libraries under modules/, with their sibling checkouts."""
    # A library is known by its mount folder (modules/stoq -> "stoq"), which is
    # how a `stoq:` reference in a BOM finds it in doqs. The name inside
    # library.toml is only a title.
    found: dict[str, LibraryCheckout] = {}
    for marker in sorted(root.rglob("library.toml")):
        mounted = marker.parent
        inner = mounted.relative_to(root).parts
        # Skip the tooling submodules at any depth (a mounted library carries
        # its own doqs, with test fixtures that are libraries too).
        if mounted == root or any(p in (".git", "doqs", ".agents", "tests", "node_modules") for p in inner):
            continue
        name = mounted.name
        found[name] = LibraryCheckout(name=name, mounted=mounted, public=None, private=None)
    if is_library_root(root):
        name = root.name.removesuffix("-private")
        found.setdefault(name, LibraryCheckout(name=name, mounted=None, public=None, private=None))
    for name, lib in found.items():
        configured = settings.libraries.get(name, {})
        public = Path(configured["public"]) if configured.get("public") else root.parent / name
        private = Path(configured["private"]) if configured.get("private") else root.parent / f"{name}-private"
        if is_library_root(root) and _is_private(root):
            private = root
        elif is_library_root(root):
            public = root
        lib.public = public if public.is_dir() and is_library_root(public) and not _is_private(public) else None
        lib.private = private if private.is_dir() and is_library_root(private) and _is_private(private) else None
    return list(found.values())


def open_workspace(root: Path | None = None, start: Path | None = None) -> Workspace:
    """A workspace at ``root``, or the nearest one above ``start`` (default: cwd)."""
    base = root.resolve() if root else find_root(start or Path.cwd())
    if not (is_machine_root(base) or is_library_root(base)):
        raise WorkspaceError(f"{base} is not a machine root (okh.toml + doqs/) or a library root (library.toml)")
    scripts = base / "doqs" / "scripts"
    if not (scripts / "cli.py").is_file():
        raise WorkspaceError(f"{base} has no doqs/scripts/cli.py: run setup-tooling.sh first")
    settings = Settings.load(base)
    kind = "library" if is_library_root(base) else "machine"
    workspace = Workspace(root=base, kind=kind, doqs_scripts=scripts, settings=settings)
    workspace.libraries = discover_libraries(base, settings)
    return workspace
