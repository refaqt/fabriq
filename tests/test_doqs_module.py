"""The doqs module through the HTTP API, on a test workspace."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fabriq.app import create_app
from fabriq.core.workspace import open_workspace


@pytest.fixture
def client(machine: Path, stub_env):
    # stub_env first: the settings read FABRIQ_FREECAD when the workspace opens.
    workspace = open_workspace(machine)
    app = create_app(workspace)
    with TestClient(app) as client:
        yield client


def wait_job(client: TestClient, job: dict, timeout: float = 90.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = client.get(f"/api/jobs/{job['id']}").json()
        if current["state"] in ("done", "failed", "cancelled"):
            return current
        time.sleep(0.1)
    raise TimeoutError(job["id"])


def test_workspace_and_modules(client: TestClient):
    info = client.get("/api/workspace").json()
    assert info["kind"] == "machine"
    assert info["doqs"]["ok"], info["doqs"]
    assert [m["name"] for m in info["modules"]] == ["doqs"]
    nav = client.get("/api/modules").json()[0]["nav"]
    assert [n["label"] for n in nav] == ["Workspace", "Modules", "Parts library", "Git"]


def test_the_read_model_sees_modules_bom_and_libraries(client: TestClient):
    model = client.get("/api/doqs/model").json()
    slugs = {m["slug"] for m in model["modules"]}
    assert "modules/linear-guide-x" in slugs
    guide = client.get("/api/doqs/model/modules/modules/linear-guide-x").json()
    assert guide["role"]["selected"] == "hiwin/hgr-rail#HGR20R500"
    assert guide["bom"][0]["part"] == "stoq:din/din-912#M4X10"
    assert guide["sysml"]["interfaces"][0]["name"] == "LinearGuide20MountInterface"
    libs = client.get("/api/doqs/library").json()
    assert libs[0]["name"] == "stoq"
    brands = {b["slug"]: b for b in libs[0]["brands"]}
    assert "hiwin" in brands
    rail = [f for f in brands["hiwin"]["families"] if f["slug"] == "hgr-rail"][0]
    part = [p for p in rail["parts"] if p["pn"] == "HGR20R500"][0]
    assert set(part["where"]) >= {"mounted", "public", "private"}
    assert model["builds"][0]["id"] == "serial-0001"


def test_scaffold_use_part_and_interface_through_the_api(client: TestClient, machine: Path, stub_env):
    report = client.post("/api/doqs/modules", json={"slug": "compact-stage", "name": "Compact Stage"}).json()
    assert report["ok"], report
    assert "modules/compact-stage/okh.toml" in report["written"]
    model = client.get("/api/doqs/model").json()
    assert "modules/compact-stage" in {m["slug"] for m in model["modules"]}

    job = client.post("/api/doqs/modules/modules/compact-stage/parts", json={"part": "base"}).json()
    done = wait_job(client, job)
    assert done["state"] == "done", done
    assert "modules/compact-stage/cad/parts/base/base.FCStd" in done["result"]["written"]

    report = client.post("/api/doqs/modules/modules/compact-stage/use-part", json={
        "part": "stoq:hiwin/hgr-rail#HGR20R500", "qty": 2, "name": "Guide rail", "usages": ["referenceRail"]}).json()
    assert report["ok"], report
    assert report["facts"]["bom_id"] == "MEC-001"
    module = client.get("/api/doqs/model/modules/modules/compact-stage").json()
    assert module["bought"][0]["part"] == "stoq:hiwin/hgr-rail#HGR20R500"
    assert module["bought"][0]["wrapper_exists"]
    assert module["parts"][0]["fingerprint"]["exists"]

    job = client.post("/api/doqs/modules/modules/compact-stage/interfaces", json={
        "name": "RailMount", "a": "base.referenceRailMount", "b": "referenceRail.baseMount",
        "outside": "provides", "doc": "The rail lies on the base."}).json()
    done = wait_job(client, job)
    assert done["state"] == "done", done
    module = client.get("/api/doqs/model/modules/modules/compact-stage").json()
    assert module["provides"][0]["name"] == "RailMountInterface"
    assert module["sysml"]["connections"][0]["a"] == "base.referenceRailMount"
    assert any(f["label"] == "IF_reference_rail_mount" for f in module["parts"][0]["frames"]) or \
        "modules/compact-stage/cad/parts/base/base.FCStd" in done["result"]["edited"]


def test_intake_and_wrap_through_the_api(client: TestClient, machine: Path, stub_env, tmp_path: Path):
    step = tmp_path / "HGL15.step"
    step.write_text(json.dumps({"solids": ["body"]}), encoding="utf-8")
    sheet = tmp_path / "hgl.pdf"
    sheet.write_bytes(b"%PDF")
    with open(step, "rb") as f_step, open(sheet, "rb") as f_sheet:
        job = client.post("/api/doqs/library/intake",
                          data={"brand": "hiwin", "family": "hgl-block", "pn": "HGL15", "description": "Block",
                                "decision": "customers", "basis": "terms", "reviewer": "N. B.",
                                "source_url": "https://x", "no_validate": "true"},
                          files={"step": ("HGL15.step", f_step), "datasheet": ("hgl.pdf", f_sheet)}).json()
    done = wait_job(client, job)
    assert done["state"] == "done", done
    private = machine.parent / "stoq-private" / "modules" / "hiwin" / "modules" / "hgl-block"
    assert (private / "cad" / "original" / "HGL15.step").is_file()
    assert not (machine.parent / "stoq" / "modules" / "hiwin" / "modules" / "hgl-block" / "cad" / "original" / "HGL15.step").exists()
    libs = client.get("/api/doqs/library").json()
    hiwin = [b for b in libs[0]["brands"] if b["slug"] == "hiwin"][0]
    block = [f for f in hiwin["families"] if f["slug"] == "hgl-block"][0]
    assert block["parts"][0]["where"]["private"]["terms"] == "internal"
    assert block["parts"][0]["where"]["public"]["terms"] == "fetch-only"

    job = client.post("/api/doqs/library/wrap", json={"part": "hiwin/hgl-block#HGL15", "frames": ["IF_rail"],
                                                      "mode": "gui"}).json()
    done = wait_job(client, job)
    assert done["state"] == "done", done
    assert (private / "cad" / "parts" / "HGL15.FCStd").is_file()


def test_check_runs_as_a_job_and_fails_loudly(client: TestClient):
    job = client.post("/api/doqs/check", json={"args": ["--only", "okh"]}).json()
    done = wait_job(client, job)
    assert done["state"] == "done", done
    assert any("validate_okh.py" in line for line in done["steps"][0]["log"])


def test_git_and_freecad_status(client: TestClient):
    status = client.get("/api/doqs/git/status").json()
    assert status["machine"]["git"] is False  # the fixture copy is not a git checkout
    fc = client.get("/api/doqs/freecad").json()
    assert "rpc" in fc and "mode" in fc
