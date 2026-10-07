"""The shell: workspace discovery, the doqs bridge, jobs and events."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from fabriq.core import workspace as ws
from fabriq.core.doqs_bridge import DoqsError, load_doqs, run_doqs
from fabriq.core.events import Broker
from fabriq.core.jobs import JobRunner


def test_find_root_walks_up_and_sees_the_libraries(machine: Path):
    deep = machine / "modules" / "x-stage" / "cad"
    deep.mkdir(parents=True, exist_ok=True)
    assert ws.find_root(deep) == machine
    workspace = ws.open_workspace(start=deep)
    assert workspace.kind == "machine"
    assert workspace.doqs_scripts == machine / "doqs" / "scripts"
    names = {lib.name: lib for lib in workspace.libraries}
    assert "stoq" in names
    lib = names["stoq"]
    assert lib.mounted == machine / "modules" / "stoq"
    assert lib.public == machine.parent / "stoq"
    assert lib.private == machine.parent / "stoq-private"


def test_a_folder_without_doqs_is_refused(tmp_path: Path):
    (tmp_path / "okh.toml").write_text("name = 'x'\n", encoding="utf-8")
    with pytest.raises(ws.WorkspaceError):
        ws.find_root(tmp_path)


def test_local_settings_override_library_paths(machine: Path, tmp_path: Path):
    other = tmp_path / "elsewhere"
    (other).mkdir()
    (other / "library.toml").write_text('schema = "doqs-library-v1"\nname = "stoq"\n', encoding="utf-8")
    local = machine / ".fabriq"
    local.mkdir()
    (local / "local.toml").write_text(
        f'[libraries.stoq]\npublic = "{other.as_posix()}"\n[freecad]\nmode = "gui"\n', encoding="utf-8")
    workspace = ws.open_workspace(machine)
    assert workspace.libraries[0].public == other
    assert workspace.settings.freecad_mode == "gui"


def test_the_bridge_loads_doqs_api_and_runs_commands(machine: Path):
    api = load_doqs(machine / "doqs" / "scripts")
    assert api.API_VERSION[0] == 1
    assert callable(api.install_module)
    result = run_doqs(machine, ["list"])
    assert result.ok
    assert "add-part" in result.stdout


def test_an_old_doqs_is_a_clear_error(tmp_path: Path):
    scripts = tmp_path / "old" / "doqs" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "cli.py").write_text("", encoding="utf-8")
    with pytest.raises(DoqsError) as err:
        load_doqs(scripts)
    assert "bump the doqs pin" in str(err.value) or "too old" in str(err.value)


@pytest.mark.asyncio
async def test_jobs_run_report_steps_and_persist(tmp_path: Path):
    broker = Broker()
    broker.bind(asyncio.get_running_loop())
    runner = JobRunner(tmp_path / "jobs", broker)
    received = []

    async def listen():
        async for event in broker.subscribe():
            received.append(event)
            if event.get("job", {}).get("state") in ("done", "failed"):
                break

    listener = asyncio.create_task(listen())
    await asyncio.sleep(0.05)

    def work(ctx):
        ctx.step("first")
        ctx.log("hello")
        ctx.step("second")
        return {"answer": 42}

    job = runner.submit("test", "A test job", work)
    done = await runner.wait(job.id)
    await asyncio.wait_for(listener, 5)
    assert done.state == "done"
    assert done.result == {"answer": 42}
    assert [s.name for s in done.steps] == ["first", "second"]
    assert all(s.state == "done" for s in done.steps)
    assert any(e["type"] == "job.updated" for e in received)
    # Persisted, and a restart marks a job that was running as failed.
    saved = (tmp_path / "jobs" / f"{job.id}.json").read_text(encoding="utf-8")
    assert '"answer": 42' in saved
    again = JobRunner(tmp_path / "jobs", broker)
    assert again.get(job.id).state == "done"

    def boom(ctx):
        ctx.step("explode")
        raise RuntimeError("no")

    failed = await runner.wait(runner.submit("test", "fails", boom).id)
    assert failed.state == "failed"
    assert failed.error == "no"
    assert failed.steps[-1].state == "failed"


@pytest.mark.asyncio
async def test_one_freecad_job_at_a_time(tmp_path: Path):
    broker = Broker()
    broker.bind(asyncio.get_running_loop())
    runner = JobRunner(tmp_path / "jobs", broker)
    order = []

    def slow(name):
        def run(ctx):
            order.append(f"start {name}")
            time.sleep(0.2)
            order.append(f"end {name}")
        return run

    a = runner.submit("f", "a", slow("a"), lock="freecad")
    b = runner.submit("f", "b", slow("b"), lock="freecad")
    await runner.wait(a.id)
    await runner.wait(b.id)
    assert order in (["start a", "end a", "start b", "end b"], ["start b", "end b", "start a", "end a"])
