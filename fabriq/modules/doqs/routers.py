"""The routes of the doqs module, under ``/api/doqs``."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from fabriq.core.git import repo_status
from fabriq.modules.doqs import services
from fabriq.modules.doqs.readmodel import ReadModel


def build_router(app) -> APIRouter:
    router = APIRouter()
    state = app.state.fabriq
    workspace = state.workspace
    model = ReadModel(workspace, state.doqs)
    state.readmodel = model

    def api():
        if state.doqs is None:
            raise HTTPException(503, state.doqs_error or "doqs is not loaded")
        return state.doqs

    def changed() -> None:
        model.invalidate()
        state.broker.publish({"type": "model.changed"})

    def finish(fn):
        """Run a job function, then tell the browser the model changed."""
        def wrapped(context):
            try:
                return fn(context)
            finally:
                changed()
        return wrapped

    # --- read ------------------------------------------------------------
    @router.get("/model")
    def get_model() -> dict:
        return model.get()

    @router.get("/model/modules/{slug:path}")
    def get_module(slug: str) -> dict:
        for module in model.get()["modules"]:
            if module["slug"] == slug:
                return module
        raise HTTPException(404, f"no module {slug}")

    @router.get("/library")
    def get_library() -> list[dict]:
        return model.get()["libraries"]

    @router.get("/freecad")
    def freecad_status() -> dict:
        a = api()
        return {
            "rpc": a.rpc_available(workspace.settings.rpc_url),
            "gui": a.find_freecad(workspace.settings.freecad, gui=True),
            "cmd": a.find_freecad(workspace.settings.freecad, gui=False),
            "mode": workspace.settings.freecad_mode,
        }

    @router.get("/git/status")
    def git_status() -> dict:
        repos = {"machine": workspace.root}
        for lib in workspace.libraries:
            if lib.private:
                repos[f"{lib.name}-private"] = lib.private
            if lib.public:
                repos[lib.name] = lib.public
        return {name: repo_status(path) for name, path in repos.items()}

    # --- write: fast ones answer at once ---------------------------------
    @router.post("/modules")
    def scaffold_module(body: dict[str, Any]) -> dict:
        report = services.scaffold_module(api(), workspace, body)
        changed()
        return report

    @router.post("/modules/{slug:path}/use-part")
    def use_part(slug: str, body: dict[str, Any]) -> dict:
        report = services.use_part(api(), workspace, {**body, "module": slug})
        changed()
        return report

    # --- write: long ones become jobs ------------------------------------
    @router.post("/modules/{slug:path}/parts")
    def scaffold_part(slug: str, body: dict[str, Any]) -> dict:
        a = api()
        job = state.jobs.submit(
            "scaffold-part", f"Create part {body.get('part')} in {slug}",
            finish(lambda ctx: services.scaffold_part(a, workspace, {**body, "module": slug}, ctx)),
            lock=None if body.get("no_cad") else "freecad")
        return job.as_dict()

    @router.post("/modules/{slug:path}/interfaces")
    def add_interface(slug: str, body: dict[str, Any]) -> dict:
        a = api()
        job = state.jobs.submit(
            "add-interface", f"Interface {body.get('name')} in {slug}",
            finish(lambda ctx: services.add_interface(a, workspace, {**body, "module": slug}, ctx)),
            lock=None if body.get("no_frames") else "freecad")
        return job.as_dict()

    @router.post("/library/intake")
    async def intake(request: Request,
                     brand: str = Form(...), family: str = Form(...), pn: str = Form(...),
                     description: str = Form(""), spec: str = Form(""), mass_g: str = Form(""),
                     source_url: str = Form(""), terms_url: str = Form(""), decision: str = Form("customers"),
                     basis: str = Form("terms"), reviewer: str = Form(""), brand_name: str = Form(""),
                     website: str = Form(""), family_name: str = Form(""), function: str = Form(""),
                     revision: str = Form("A"), notes: str = Form(""), library: str = Form(""),
                     dry_run: bool = Form(False), no_validate: bool = Form(False),
                     step: UploadFile | None = File(None), terms_pdf: UploadFile | None = File(None),
                     licence: UploadFile | None = File(None),
                     datasheet: list[UploadFile] = File([])) -> dict:
        a = api()
        upload_dir = Path(tempfile.mkdtemp(prefix="fabriq-upload-", dir=workspace.local_dir()))
        files: dict[str, Path] = {}
        for key, upload in (("step", step), ("terms_pdf", terms_pdf), ("licence", licence)):
            if upload is not None and upload.filename:
                target = upload_dir / Path(upload.filename).name
                target.write_bytes(await upload.read())
                files[key] = target
        for i, upload in enumerate(datasheet):
            if upload.filename:
                target = upload_dir / Path(upload.filename).name
                target.write_bytes(await upload.read())
                files[f"datasheet{i}"] = target
        body = {
            "brand": brand, "family": family, "pn": pn, "description": description, "spec": spec,
            "mass_g": mass_g, "source_url": source_url, "terms_url": terms_url, "decision": decision,
            "basis": basis, "reviewer": reviewer, "brand_name": brand_name or None, "website": website,
            "family_name": family_name or None, "function": function or None, "revision": revision,
            "notes": notes, "library": library or None, "dry_run": dry_run, "no_validate": no_validate,
        }

        def run(ctx):
            try:
                return services.intake(a, workspace, body, files, ctx)
            finally:
                shutil.rmtree(upload_dir, ignore_errors=True)

        job = state.jobs.submit("add-part", f"Add part {pn} to the libraries", finish(run))
        return job.as_dict()

    @router.post("/library/wrap")
    def wrap(body: dict[str, Any]) -> dict:
        a = api()
        job = state.jobs.submit("wrap", f"Wrap {body.get('part')} in FreeCAD",
                                finish(lambda ctx: services.wrap(a, workspace, body, ctx)), lock="freecad")
        return job.as_dict()

    @router.post("/check")
    def check(body: dict[str, Any] | None = None) -> dict:
        args = ["check"] + list((body or {}).get("args") or [])
        job = state.jobs.submit("check", "doqs check", lambda ctx: services.doqs_command(workspace, args, ctx))
        return job.as_dict()

    @router.post("/generate")
    def generate() -> dict:
        job = state.jobs.submit("generate", "doqs generate",
                                finish(lambda ctx: services.doqs_command(workspace, ["generate"], ctx)))
        return job.as_dict()

    return router
