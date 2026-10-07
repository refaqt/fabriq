"""Background jobs: long work with steps, logs, a result, and a record on disk.

A job runs a plain Python function in a thread (FreeCAD, git and the doqs
commands all block). The function gets a ``JobContext`` to add steps and
log lines; every change is published as ``job.updated``. Jobs are saved
under ``<root>/.fabriq/jobs/<id>.json`` so a page reload still shows them.
One job at a time per lock name (``freecad``), any number otherwise.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from fabriq.core.events import Broker

STATES = ("queued", "running", "done", "failed", "cancelled")


@dataclass
class Step:
    name: str
    state: str = "running"
    log: list[str] = field(default_factory=list)
    started: float = field(default_factory=time.time)
    finished: float | None = None


@dataclass
class Job:
    id: str
    kind: str
    title: str
    state: str = "queued"
    steps: list[Step] = field(default_factory=list)
    result: Any = None
    error: str | None = None
    created: float = field(default_factory=time.time)
    started: float | None = None
    finished: float | None = None
    lock: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


class JobContext:
    """What a job function uses to report progress."""

    def __init__(self, runner: "JobRunner", job: Job):
        self._runner = runner
        self.job = job
        self.cancelled = threading.Event()

    def step(self, name: str) -> Step:
        for previous in self.job.steps:
            if previous.state == "running":
                previous.state = "done"
                previous.finished = time.time()
        step = Step(name=name)
        self.job.steps.append(step)
        self._runner._changed(self.job)
        return step

    def log(self, line: str) -> None:
        if not self.job.steps:
            self.step("work")
        self.job.steps[-1].log.append(line)
        self._runner._changed(self.job)

    def fail_step(self, reason: str) -> None:
        if self.job.steps:
            self.job.steps[-1].state = "failed"
            self.job.steps[-1].log.append(reason)
            self.job.steps[-1].finished = time.time()
        self._runner._changed(self.job)


class JobRunner:
    def __init__(self, store: Path, broker: Broker, workers: int = 4):
        self.store = store
        self.store.mkdir(parents=True, exist_ok=True)
        self.broker = broker
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="fabriq-job")
        self._jobs: dict[str, Job] = {}
        self._contexts: dict[str, JobContext] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._mutex = threading.Lock()
        self._load()

    # --- persistence ---------------------------------------------------
    def _load(self) -> None:
        for path in sorted(self.store.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                steps = [Step(**s) for s in data.pop("steps", [])]
                job = Job(**{k: v for k, v in data.items() if k in Job.__dataclass_fields__})
                job.steps = steps
                if job.state in ("queued", "running"):
                    job.state = "failed"
                    job.error = "fabriq stopped while this job ran"
                self._jobs[job.id] = job
            except (OSError, ValueError, TypeError):
                continue

    def _save(self, job: Job) -> None:
        path = self.store / f"{job.id}.json"
        try:
            path.write_text(json.dumps(job.as_dict(), indent=1, default=str), encoding="utf-8")
        except OSError:
            pass

    def _changed(self, job: Job) -> None:
        self._save(job)
        self.broker.publish({"type": "job.updated", "job": job.as_dict()})

    # --- API -----------------------------------------------------------
    def list(self, limit: int = 50) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.created, reverse=True)[:limit]

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def submit(self, kind: str, title: str, fn: Callable[[JobContext], Any], lock: str | None = None) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], kind=kind, title=title, lock=lock)
        context = JobContext(self, job)
        with self._mutex:
            self._jobs[job.id] = job
            self._contexts[job.id] = context
        self._changed(job)
        self._executor.submit(self._run, job, context, fn)
        return job

    def cancel(self, job_id: str) -> bool:
        context = self._contexts.get(job_id)
        if context is None or context.job.state not in ("queued", "running"):
            return False
        context.cancelled.set()
        if context.job.state == "queued":
            context.job.state = "cancelled"
            context.job.finished = time.time()
            self._changed(context.job)
        return True

    def _run(self, job: Job, context: JobContext, fn: Callable[[JobContext], Any]) -> None:
        lock = None
        if job.lock:
            with self._mutex:
                lock = self._locks.setdefault(job.lock, threading.Lock())
            lock.acquire()
        try:
            if context.cancelled.is_set():
                return
            job.state = "running"
            job.started = time.time()
            self._changed(job)
            job.result = fn(context)
            for step in job.steps:
                if step.state == "running":
                    step.state = "done"
                    step.finished = time.time()
            job.state = "cancelled" if context.cancelled.is_set() else "done"
        except Exception as exc:  # noqa: BLE001 - a job must never kill the runner
            job.state = "failed"
            job.error = f"{exc}"
            context.fail_step(traceback.format_exc(limit=3))
        finally:
            job.finished = time.time()
            if lock is not None:
                lock.release()
            self._changed(job)

    async def wait(self, job_id: str, timeout: float = 60.0) -> Job:
        """Wait for a job to finish (tests and the CLI use this)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            job = self._jobs[job_id]
            if job.state in ("done", "failed", "cancelled"):
                return job
            await asyncio.sleep(0.05)
        raise TimeoutError(f"job {job_id} still running after {timeout} s")
