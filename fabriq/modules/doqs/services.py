"""The doqs commands, called from jobs. Each returns the doqs report as a dict."""
from __future__ import annotations

import json
from pathlib import Path

from fabriq.core.doqs_bridge import run_doqs
from fabriq.core.jobs import JobContext
from fabriq.core.workspace import Workspace


def _report(report) -> dict:
    return json.loads(report.to_json())


def _library(workspace: Workspace, name: str, which: str) -> Path | None:
    for lib in workspace.libraries:
        if lib.name == name:
            return getattr(lib, which)
    return None


def scaffold_module(api, workspace: Workspace, body: dict) -> dict:
    report = api.install_module(
        workspace.root, body["slug"], parent=Path(body["parent"]) if body.get("parent") else None,
        name=body.get("name"), function=body.get("function"), licensor=body.get("licensor"),
        dry_run=bool(body.get("dry_run")))
    return _report(report)


def scaffold_part(api, workspace: Workspace, body: dict, context: JobContext) -> dict:
    context.step("scaffold the part")
    report = api.install_part(
        workspace.root, Path(body["module"]), body["part"], name=body.get("name"),
        sysml=body.get("sysml"), usage=body.get("usage"), no_cad=bool(body.get("no_cad")),
        freecad=workspace.settings.freecad, mode=body.get("mode") or workspace.settings.freecad_mode,
        dry_run=bool(body.get("dry_run")))
    for line in report.warnings:
        context.log(line)
    return _report(report)


def intake(api, workspace: Workspace, body: dict, files: dict[str, Path], context: JobContext) -> dict:
    context.step("record the part in the libraries")
    library = body.get("library") or (workspace.libraries[0].name if workspace.libraries else "stoq")
    private = _library(workspace, library, "private")
    public = _library(workspace, library, "public")
    report = api.intake(
        private=private, public=public, brand=body["brand"], family=body["family"], pn=body["pn"],
        description=body.get("description", ""), spec=body.get("spec", ""), mass_g=body.get("mass_g", ""),
        step=files.get("step"), datasheets=[p for k, p in files.items() if k.startswith("datasheet")],
        terms_pdf=files.get("terms_pdf"), licence=files.get("licence"),
        source_url=body.get("source_url", ""), terms_url=body.get("terms_url", ""),
        decision=body.get("decision", "customers"), basis=body.get("basis", "terms"),
        reviewer=body.get("reviewer", workspace.settings.github_user), brand_name=body.get("brand_name"),
        website=body.get("website", ""), family_name=body.get("family_name"), function=body.get("function"),
        revision=body.get("revision", "A"), notes=body.get("notes", ""),
        validate=not body.get("no_validate"), dry_run=bool(body.get("dry_run")))
    return _report(report)


def wrap(api, workspace: Workspace, body: dict, context: JobContext) -> dict:
    context.step("wrap the STEP file in FreeCAD")
    library = body.get("library") or (workspace.libraries[0].name if workspace.libraries else "stoq")
    private = _library(workspace, library, "private")
    public = _library(workspace, library, "public")
    source = private or public
    if source is None:
        raise RuntimeError(f"no checkout of {library} beside the workspace; set it in .fabriq/local.toml")
    mirror = public if source is private else None
    report = api.wrap_part(
        source, body["part"], frames=list(body.get("frames") or []), label=body.get("label"),
        mirror=mirror, mode=body.get("mode") or workspace.settings.freecad_mode,
        freecad=workspace.settings.freecad, dry_run=bool(body.get("dry_run")))
    for line in report.facts.get("freecad_steps", []):
        context.log(line)
    return _report(report)


def use_part(api, workspace: Workspace, body: dict) -> dict:
    report = api.use_part(
        workspace.root, Path(body["module"]), body["part"], qty=str(body.get("qty", "1")),
        name=body.get("name"), category=body.get("category", "MEC"), unit=body.get("unit", "pc"),
        equiv_class=body.get("equiv_class", ""), notes=body.get("notes", ""), sysml=body.get("sysml"),
        usages=list(body.get("usages") or []), library=body.get("library_mount"),
        bump=body.get("bump_pin"), allow_unmerged=bool(body.get("allow_unmerged")),
        generate=bool(body.get("generate")), dry_run=bool(body.get("dry_run")))
    return _report(report)


def add_interface(api, workspace: Workspace, body: dict, context: JobContext) -> dict:
    context.step("write the interface to SysML, okh.toml and the part files")
    library_checkout = None
    if body.get("library"):
        library_checkout = _library(workspace, body["library"], "private") or _library(workspace, body["library"], "public")
    report = api.add_interface(
        workspace.root, Path(body["module"]), body["name"], body["a"], body["b"],
        major=int(body.get("major", 1)), doc=body.get("doc"), attributes=list(body.get("attributes") or []),
        outside=body.get("outside"), frames=not body.get("no_frames"), library_checkout=library_checkout,
        mode=body.get("mode") or workspace.settings.freecad_mode, freecad=workspace.settings.freecad,
        dry_run=bool(body.get("dry_run")))
    return _report(report)


def doqs_command(workspace: Workspace, args: list[str], context: JobContext) -> dict:
    context.step(f"doqs {' '.join(args)}")
    result = run_doqs(workspace.root, args)
    for line in (result.stdout + result.stderr).splitlines():
        context.log(line)
    if not result.ok:
        raise RuntimeError(f"doqs {' '.join(args)} exited {result.returncode}")
    return {"ok": result.ok, "returncode": result.returncode, "output": result.stdout}
