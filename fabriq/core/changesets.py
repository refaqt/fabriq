"""One change across repositories: branches, commits, pull requests, pin bumps.

A change set has a topic, the designer's comment, and one entry per
repository it touches, in the fixed order private library, public library,
machine. Each entry collects the doqs reports that wrote there, the files
git sees as changed, the generated commit message and pull request text
(editable), and later the commit, the pull request and its state.

The rules it keeps:

- the branch is ``feat/<topic>``, the same name in every repository;
- a library change always goes through a pull request; the machine's pin
  moves only to a merged commit (``bump_pin`` in doqs refuses the rest);
- a machine commit is refused while a mounted library has local changes
  (the stray-edit incident), and the panel says which files.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from fabriq.core import git as g
from fabriq.core import github, reporting
from fabriq.core.jobs import JobContext
from fabriq.core.workspace import Workspace

ORDER = ("private", "public", "machine")


@dataclass
class RepoChange:
    name: str
    path: str
    kind: str                      # private | public | machine
    branch: str
    files: list[str] = field(default_factory=list)
    reports: list[dict] = field(default_factory=list)
    commit_message: str = ""
    pr_title: str = ""
    pr_body: str = ""
    commit: str | None = None
    pr_url: str | None = None
    pr_state: str | None = None
    merge_commit: str | None = None
    pin_bumped: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class ChangeSet:
    id: str
    topic: str
    comment: str
    created: float
    repos: list[RepoChange] = field(default_factory=list)
    state: str = "draft"           # draft | committed | pushed | merged | done

    def as_dict(self) -> dict:
        return asdict(self)

    def repo(self, name: str) -> RepoChange | None:
        return next((r for r in self.repos if r.name == name), None)


def slugify(topic: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return slug or "change"


class ChangeSets:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.store = workspace.local_dir() / "changesets"
        self.store.mkdir(parents=True, exist_ok=True)

    # --- persistence ---------------------------------------------------
    def _path(self, cs_id: str) -> Path:
        return self.store / f"{cs_id}.json"

    def save(self, cs: ChangeSet) -> None:
        self._path(cs.id).write_text(json.dumps(cs.as_dict(), indent=1), encoding="utf-8")

    def get(self, cs_id: str) -> ChangeSet | None:
        path = self._path(cs_id)
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        repos = [RepoChange(**r) for r in data.pop("repos", [])]
        cs = ChangeSet(**data)
        cs.repos = repos
        return cs

    def list(self) -> list[ChangeSet]:
        out = [self.get(p.stem) for p in sorted(self.store.glob("*.json"))]
        return sorted([c for c in out if c], key=lambda c: c.created, reverse=True)

    # --- repositories --------------------------------------------------
    def repositories(self) -> list[tuple[str, Path, str]]:
        """``(name, path, kind)`` in the order a change lands."""
        found: list[tuple[str, Path, str]] = []
        for lib in self.workspace.libraries:
            if lib.private and (lib.private / ".git").exists():
                found.append((f"{lib.name}-private", lib.private, "private"))
        for lib in self.workspace.libraries:
            if lib.public and (lib.public / ".git").exists():
                found.append((lib.name, lib.public, "public"))
        if (self.workspace.root / ".git").exists():
            found.append(("machine", self.workspace.root, "machine"))
        return found

    def dirty_files(self, path: Path) -> list[str]:
        status = g.repo_status(path)
        return status.get("dirty", []) if status.get("git") else []

    def stray_library_edits(self) -> list[str]:
        """Files changed inside a mounted library, which the machine must not commit."""
        stray = []
        for lib in self.workspace.libraries:
            if lib.mounted and (lib.mounted / ".git").exists():
                for f in self.dirty_files(lib.mounted):
                    stray.append(f"{lib.mounted.relative_to(self.workspace.root).as_posix()}/{f}")
        return stray

    # --- building ------------------------------------------------------
    def create(self, topic: str, comment: str, reports_by_root: dict[str, list[dict]],
               only: list[str] | None = None, commit_types: tuple[str, ...] = ()) -> ChangeSet:
        branch = f"feat/{slugify(topic)}"
        cs = ChangeSet(id=uuid.uuid4().hex[:10], topic=topic, comment=comment, created=time.time())
        every = [r for reports in reports_by_root.values() for r in reports]
        for name, path, kind in self.repositories():
            if only and name not in only:
                continue
            files = self.dirty_files(path)
            key = str(path.resolve())
            reports = list(reports_by_root.get(key, []))
            # A command that wrote in several repositories (add-part) names them all.
            for report in every:
                roots = {str(Path(r).resolve()) for r in (report.get("facts") or {}).get("roots", [])}
                if key in roots and report not in reports:
                    reports.append(report)
            if not files and not reports:
                continue
            repo = RepoChange(name=name, path=str(path), kind=kind, branch=branch, files=files, reports=reports)
            scope = reporting._scope(reports[0], path.name) if reports else path.name
            repo.commit_message = reporting.commit_message(reports, comment, scope=scope, commit_types=commit_types)
            repo.pr_title = reporting.pr_title(reports, topic)
            repo.pr_body = reporting.pr_body(reports, comment, files=files)
            cs.repos.append(repo)
        self.save(cs)
        return cs

    def update_text(self, cs: ChangeSet, name: str, commit_message: str | None = None,
                    pr_title: str | None = None, pr_body: str | None = None) -> ChangeSet:
        repo = cs.repo(name)
        if repo is None:
            raise KeyError(name)
        if commit_message is not None:
            repo.commit_message = commit_message
        if pr_title is not None:
            repo.pr_title = reporting.clip(pr_title)
        if pr_body is not None:
            problems = reporting.check_body(pr_body)
            if problems:
                raise ValueError("; ".join(problems))
            repo.pr_body = pr_body
        self.save(cs)
        return cs

    # --- acting --------------------------------------------------------
    def commit(self, cs: ChangeSet, context: JobContext | None = None) -> ChangeSet:
        """Branch and commit in every repository, in order. Refuses stray library edits."""
        stray = self.stray_library_edits()
        if stray and any(r.kind == "machine" for r in cs.repos):
            raise RuntimeError(
                "the machine has changes inside a mounted library, which belong in the library "
                "checkout: " + ", ".join(stray))
        for kind in ORDER:
            for repo in [r for r in cs.repos if r.kind == kind]:
                path = Path(repo.path)
                if context:
                    context.step(f"{repo.name}: branch {repo.branch} and commit")
                g.create_branch(path, repo.branch, base="HEAD")
                files = self.dirty_files(path) or repo.files
                sha = g.commit(path, files, repo.commit_message)
                repo.commit = sha
                repo.notes.append(f"committed {sha[:10]}" if sha else "nothing to commit")
                if context:
                    context.log(repo.notes[-1])
        cs.state = "committed"
        self.save(cs)
        return cs

    def push_and_pr(self, cs: ChangeSet, context: JobContext | None = None, base: str = "main") -> ChangeSet:
        for kind in ORDER:
            for repo in [r for r in cs.repos if r.kind == kind]:
                path = Path(repo.path)
                if context:
                    context.step(f"{repo.name}: push and open the pull request")
                g.push(path, repo.branch)
                if repo.pr_url:
                    continue
                related = [r.pr_url for r in cs.repos if r.pr_url and r is not repo]
                body = repo.pr_body
                if related:
                    body = body.replace("</details>", "- Related pull requests: " + ", ".join(related) + "\n\n</details>")
                repo.pr_url = github.create_pr(path, repo.pr_title, body, base=base, head=repo.branch)
                repo.pr_state = "OPEN"
                if context:
                    context.log(f"opened {repo.pr_url}")
        cs.state = "pushed"
        self.save(cs)
        return cs

    def refresh(self, cs: ChangeSet) -> ChangeSet:
        for repo in cs.repos:
            if repo.pr_url:
                try:
                    state = github.pr_state(Path(repo.path), repo.pr_url)
                except github.GitHubError as exc:
                    repo.notes.append(f"could not read the pull request: {exc}")
                    continue
                repo.pr_state = state["state"]
                repo.merge_commit = state.get("merge_commit")
        if cs.repos and all(r.pr_state == "MERGED" for r in cs.repos if r.kind != "machine"):
            if cs.state == "pushed":
                cs.state = "merged"
        self.save(cs)
        return cs

    def bump_after_merge(self, cs: ChangeSet, api, context: JobContext | None = None,
                         poll: float = 30.0, timeout: float = 6 * 3600) -> ChangeSet:
        """Wait for the library pull requests to merge, then move the machine's pins."""
        libraries = [r for r in cs.repos if r.kind == "public" and r.pr_url]
        machine = self.workspace.root
        deadline = time.monotonic() + timeout
        while True:
            self.refresh(cs)
            waiting = [r for r in libraries if r.pr_state != "MERGED"]
            if not waiting:
                break
            if context:
                if context.cancelled.is_set():
                    raise RuntimeError("cancelled while waiting for the merge")
                context.log("waiting for the merge of " + ", ".join(r.pr_url or r.name for r in waiting))
            if time.monotonic() > deadline:
                raise RuntimeError("gave up waiting for the merge")
            time.sleep(poll)
        for repo in libraries:
            mount = next((lib.mounted for lib in self.workspace.libraries if lib.name == repo.name), None)
            if mount is None or repo.merge_commit is None:
                continue
            rel = mount.relative_to(machine).as_posix()
            if context:
                context.step(f"move the pin of {rel} to {repo.merge_commit[:10]}")
            sha, message = api.bump_pin(machine, rel, repo.merge_commit)
            if sha is None:
                raise RuntimeError(message)
            repo.pin_bumped = sha
            if context:
                context.log(message)
        cs.state = "done"
        self.save(cs)
        return cs
