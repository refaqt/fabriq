"""The design as the browser sees it, read from the files in the workspace.

Nothing here writes. Everything comes from `okh.toml`, the BOM and parameter
tables, the SysML files, the build records, the saved FreeCAD documents
(read without FreeCAD) and the library tables, through ``doqs_api``. The
model is cached and rebuilt when the signature of those files changes.
"""
from __future__ import annotations

import csv
import io
import json
import os
import tomllib
from pathlib import Path
from types import ModuleType

from fabriq.core.workspace import Workspace

WATCHED_SUFFIXES = (".toml", ".sysml", ".csv", ".FCStd", ".json")
SKIP_DIRS = {".git", ".fabriq", "doqs", ".agents", "node_modules", "__pycache__", ".venv"}


def signature(root: Path) -> tuple[int, float]:
    """``(file count, newest mtime)`` over the files the model reads."""
    count, newest = 0, 0.0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(WATCHED_SUFFIXES):
                count += 1
                try:
                    newest = max(newest, os.stat(os.path.join(dirpath, name)).st_mtime)
                except OSError:
                    continue
    return count, newest


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    body = "".join(l for l in text.splitlines(keepends=True) if not l.lstrip().startswith("#"))
    return [dict(r) for r in csv.DictReader(io.StringIO(body))]


def _toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


class ReadModel:
    def __init__(self, workspace: Workspace, api: ModuleType | None):
        self.workspace = workspace
        self.api = api
        self._cached: dict | None = None
        self._signature: tuple[int, float] | None = None

    def invalidate(self) -> None:
        self._cached = None

    def get(self) -> dict:
        sig = signature(self.workspace.root)
        if self._cached is None or sig != self._signature:
            self._cached = self.build()
            self._signature = sig
        return self._cached

    # --- building ------------------------------------------------------
    def build(self) -> dict:
        root = self.workspace.root
        libraries = self._libraries()
        mounted = {Path(lib["mounted"]) for lib in libraries if lib.get("mounted")}
        modules = [self._module(root, d, libraries) for d in self._module_dirs(root, mounted)]
        return {
            "root": str(root),
            "kind": self.workspace.kind,
            "modules": modules,
            "libraries": libraries,
            "builds": self._builds(root),
            "problems": [p for m in modules for p in m["problems"]],
        }

    def _module_dirs(self, root: Path, mounted: set[Path]) -> list[Path]:
        found = []
        for okh in sorted(root.rglob("okh.toml")):
            parent = okh.parent
            if any(part in SKIP_DIRS for part in parent.relative_to(root).parts):
                continue
            if any(parent == m or m in parent.parents for m in mounted):
                continue
            found.append(parent)
        return found

    def _module(self, root: Path, module_dir: Path, libraries: list[dict]) -> dict:
        api = self.api
        data = _toml(module_dir / "okh.toml")
        slug = _rel(root, module_dir) or "."
        problems: list[str] = []
        sysml = self._sysml(module_dir)
        part_defs = {p["name"] for p in sysml["parts"]}
        parts = []
        for entry in data.get("part", []) or []:
            sources = entry.get("source") or []
            fcstd = module_dir / sources[0] if sources else None
            parts.append({
                "name": entry.get("name"), "sysml": entry.get("sysml"),
                "file": _rel(root, fcstd) if fcstd else None,
                "exists": bool(fcstd and fcstd.is_file()),
                "frames": self._frames(fcstd) if fcstd and fcstd.is_file() else [],
                "fingerprint": self._fingerprint(fcstd) if fcstd else None,
                "build_script": bool(fcstd and (fcstd.parent / "build_model.py").is_file()),
            })
            if entry.get("sysml") and entry["sysml"] not in part_defs:
                problems.append(f"{slug}: [[part]] {entry.get('name')} names part def {entry['sysml']}, which is not in the SysML")
        bought = []
        for entry in data.get("bought-part", []) or []:
            ref = str(entry.get("part", ""))
            resolved = self._resolve_reference(root, ref)
            bought.append({"bom": entry.get("bom"), "part": ref, "sysml": entry.get("sysml"), **resolved})
            if resolved.get("error"):
                problems.append(f"{slug}: {resolved['error']}")
        bom = _rows(module_dir / (data.get("bom") or "bom/bom.csv"))
        params = _rows(module_dir / "cad" / "params" / "default.csv")
        return {
            "slug": slug,
            "name": data.get("name"),
            "version": data.get("version"),
            "function": data.get("function"),
            "provides": [{"name": e.get("name"), "version": e.get("version"), "description": e.get("description")}
                         for e in data.get("provides-interface", []) or []],
            "consumes": [{"name": e.get("name"), "version": e.get("version"), "description": e.get("description")}
                         for e in data.get("consumes-interface", []) or []],
            "components": [e.get("component") for e in data.get("hasComponent", []) or []],
            "parts": parts,
            "bought": bought,
            "bom": bom,
            "params": params,
            "sysml": sysml,
            "role": data.get("role"),
            "problems": problems,
        }

    def _sysml(self, module_dir: Path) -> dict:
        api = self.api
        out = {"files": [], "interfaces": [], "parts": [], "connections": [], "requirements": []}
        arch = module_dir / "architecture"
        if api is None or not arch.is_dir():
            return out
        for path in sorted(arch.glob("*.sysml")):
            text = path.read_text(encoding="utf-8")
            tree = api.parse_sysml(text)
            out["files"].append(path.name)
            out["interfaces"] += api.interfaces(tree)
            out["parts"] += api.parts(tree)
            out["connections"] += [{"owner": o, "a": a, "b": b} for o, a, b in api.connections(tree)]
            out["requirements"] += api.requirements(tree)
        return out

    def _frames(self, fcstd: Path) -> list[dict]:
        if self.api is None:
            return []
        return [{"name": n, "label": l} for n, l in self.api.frames(fcstd)]

    def _fingerprint(self, fcstd: Path) -> dict | None:
        path = fcstd.with_name(fcstd.stem + ".fingerprint.json")
        if not path.is_file():
            return {"exists": False, "current": False}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"exists": True, "current": False}
        current = False
        if fcstd.is_file() and self.api is not None:
            from hashlib import sha256
            digest = sha256(fcstd.read_bytes()).hexdigest()
            current = (data.get("sources") or {}).get(fcstd.name) == digest
        unlinked = 0
        for obj in (data.get("parametric") or {}).get("objects", {}).values():
            unlinked += len(obj.get("unlinked", []))
        return {"exists": True, "current": current, "saved": bool(data.get("saved")), "unlinked": unlinked}

    def _resolve_reference(self, root: Path, ref: str) -> dict:
        api = self.api
        if api is None or ":" not in ref:
            return {"error": f"{ref!r} is not a library reference"}
        lib, _, part = ref.partition(":")
        mounts = api.mounted_libraries(root)
        mount = next((m for m in mounts if Path(m).name == lib), None)
        if mount is None:
            return {"error": f"no library {lib!r} is mounted for {ref}"}
        row, detail = api.library_part(root, mount, part)
        if row is None:
            return {"error": f"{ref}: {detail}"}
        cad = (row.get("cad") or "").strip()
        wrapper = root / mount / detail / cad if cad else None
        return {
            "description": row.get("description"), "spec": row.get("spec"), "terms": row.get("terms"),
            "status": row.get("status"), "unit_mass_g": row.get("unit_mass_g"),
            "wrapper": _rel(root, wrapper) if wrapper else None,
            "wrapper_exists": bool(wrapper and wrapper.is_file()),
            "frames": self._frames(wrapper) if wrapper and wrapper.is_file() else [],
            "library": mount, "family": detail,
        }

    def _libraries(self) -> list[dict]:
        out = []
        for lib in self.workspace.libraries:
            entry = lib.as_dict()
            roots = {"mounted": lib.mounted, "public": lib.public, "private": lib.private}
            entry["brands"] = self._brands({k: v for k, v in roots.items() if v and v.is_dir()})
            out.append(entry)
        return out

    def _brands(self, roots: dict[str, Path]) -> list[dict]:
        brands: dict[str, dict] = {}
        for where, root in roots.items():
            modules = root / "modules"
            if not modules.is_dir():
                continue
            for brand_okh in sorted(modules.glob("*/okh.toml")):
                brand_dir = brand_okh.parent
                data = _toml(brand_okh)
                brand = brands.setdefault(brand_dir.name, {
                    "slug": brand_dir.name, "name": data.get("name"), "website": (data.get("brand") or {}).get("website"),
                    "reviews": [], "families": {},
                })
                if where in ("public", "mounted") or not brand["reviews"]:
                    brand["reviews"] = [
                        {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()}
                        for r in data.get("terms-review", []) or []
                    ]
                for fam_okh in sorted((brand_dir / "modules").glob("*/okh.toml")):
                    fam_dir = fam_okh.parent
                    fam_data = _toml(fam_okh)
                    family = brand["families"].setdefault(fam_dir.name, {
                        "slug": fam_dir.name, "name": fam_data.get("name"), "function": fam_data.get("function"),
                        "provides": [e.get("name") for e in fam_data.get("provides-interface", []) or []],
                        "parts": {},
                    })
                    for row in _rows(fam_dir / "bom" / "parts.csv"):
                        pn = (row.get("pn") or "").strip()
                        if not pn:
                            continue
                        part = family["parts"].setdefault(pn, {
                            "pn": pn, "description": row.get("description"), "spec": row.get("spec"),
                            "unit_mass_g": row.get("unit_mass_g"), "status": row.get("status"),
                            "reference": f"{brand_dir.name}/{fam_dir.name}#{pn}", "where": {},
                        })
                        cad = (row.get("cad") or "").strip()
                        wrapper = fam_dir / cad if cad else None
                        part["where"][where] = {
                            "terms": row.get("terms"), "cad": cad,
                            "cad_exists": bool(wrapper and wrapper.is_file()),
                            "frames": self._frames(wrapper) if wrapper and wrapper.is_file() else [],
                            "datasheet": row.get("datasheet"),
                        }
        out = []
        for brand in brands.values():
            brand["families"] = [
                {**f, "parts": list(f["parts"].values())} for f in brand["families"].values()
            ]
            out.append(brand)
        return out

    def _builds(self, root: Path) -> list[dict]:
        out = []
        for build in sorted((root / "builds").glob("*/build.toml")) if (root / "builds").is_dir() else []:
            data = _toml(build)
            out.append({"id": build.parent.name, "base": data.get("base"), "modules": data.get("module", [])})
        return out
