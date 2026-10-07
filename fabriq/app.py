"""The FastAPI application: core routes, every module's routes, the built frontend."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from fabriq import __version__
from fabriq.core import registry
from fabriq.core.doqs_bridge import DoqsError, load_doqs
from fabriq.core.events import Broker
from fabriq.core.jobs import JobRunner
from fabriq.core.workspace import Workspace

STATIC = Path(__file__).resolve().parent / "static"


class State:
    """What every route reaches through ``app.state.fabriq``."""

    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.broker = Broker()
        self.jobs = JobRunner(workspace.local_dir() / "jobs", self.broker)
        self.modules: dict[str, registry.ModuleManifest] = {}
        self.doqs = None
        self.doqs_error: str | None = None
        try:
            self.doqs = load_doqs(workspace.doqs_scripts)
        except DoqsError as exc:
            self.doqs_error = str(exc)


def create_app(workspace: Workspace) -> FastAPI:
    state = State(workspace)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state.broker.bind(asyncio.get_running_loop())
        yield

    app = FastAPI(title="fabriq", version=__version__, lifespan=lifespan)
    app.state.fabriq = state

    @app.get("/api/workspace")
    def workspace_info() -> dict:
        api = state.doqs
        return {
            **workspace.as_dict(),
            "fabriq": __version__,
            "doqs": {
                "ok": api is not None,
                "api_version": list(getattr(api, "API_VERSION_FOUND", ())) if api else None,
                "error": state.doqs_error,
            },
            "modules": [m.as_dict() for m in state.modules.values()],
        }

    @app.get("/api/modules")
    def modules() -> list[dict]:
        return [m.as_dict() for m in state.modules.values()]

    @app.get("/api/events")
    async def events():
        async def stream():
            yield state.broker.format({"type": "hello", "fabriq": __version__})
            async for event in state.broker.subscribe():
                yield state.broker.format(event)
        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/jobs")
    def jobs(limit: int = 50) -> list[dict]:
        return [j.as_dict() for j in state.jobs.list(limit)]

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str) -> dict:
        found = state.jobs.get(job_id)
        if found is None:
            raise HTTPException(404, f"no job {job_id}")
        return found.as_dict()

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str) -> dict:
        return {"cancelled": state.jobs.cancel(job_id)}

    for name, register in registry.discover().items():
        manifest = register(app)
        state.modules[name] = manifest
        if manifest.router is not None:
            app.include_router(manifest.router, prefix=f"/api/{name}", tags=[name])

    if (STATIC / "index.html").is_file():
        if (STATIC / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            candidate = STATIC / path
            if path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(STATIC / "index.html")

    return app
