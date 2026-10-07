"""Change sets: generated text, commits in order, pull requests, pin bumps.

Real git repositories with bare remotes stand in for GitHub's clones; a fake
`gh` on PATH stands in for GitHub itself. The library's main branch is the
real one, so a pin bump proves the merged commit is used.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from fabriq.core import reporting
from fabriq.core.changesets import ChangeSets, slugify
from fabriq.core.doqs_bridge import load_doqs
from fabriq.core.workspace import open_workspace

GIT = ["-c", "user.name=T", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]
FAKE_GH = '''
import json, sys, os, subprocess
from pathlib import Path
store = Path(os.environ["FAKE_GH_STORE"])
args = sys.argv[1:]
if args[:2] == ["pr", "create"]:
    body = sys.stdin.read()
    title = args[args.index("--title") + 1]
    head = args[args.index("--head") + 1] if "--head" in args else "?"
    data = json.loads(store.read_text()) if store.is_file() else {}
    n = len(data) + 1
    url = f"https://github.example/org/repo/pull/{n}"
    data[url] = {"state": "OPEN", "title": title, "body": body, "head": head, "cwd": os.getcwd()}
    store.write_text(json.dumps(data))
    print(url)
elif args[:2] == ["pr", "view"]:
    data = json.loads(store.read_text())
    pr = data[args[2]]
    print(json.dumps({"state": pr["state"], "mergedAt": None, "mergeCommit": {"oid": pr.get("merge")} if pr.get("merge") else None,
                      "url": args[2], "number": 1, "statusCheckRollup": []}))
else:
    sys.exit(2)
'''


def git(path: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(path), *GIT, *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _init_with_remote(path: Path, remote: Path) -> None:
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    if not (path / ".git").exists():
        subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "start")
    git(path, "remote", "add", "origin", str(remote))
    git(path, "push", "-q", "-u", "origin", "main")


@pytest.fixture
def repos(machine: Path, tmp_path: Path, monkeypatch) -> dict:
    """The machine, the public and the private library as git repos with remotes."""
    remotes = tmp_path / "remotes"
    remotes.mkdir()
    public, private = tmp_path / "stoq", tmp_path / "stoq-private"
    _init_with_remote(private, remotes / "stoq-private.git")
    _init_with_remote(public, remotes / "stoq.git")
    # The machine mounts the public library as a real submodule at modules/stoq.
    shutil.rmtree(machine / "modules" / "stoq")
    subprocess.run(["git", "init", "-q", "-b", "main", str(machine)], check=True)
    subprocess.run(["git", "-C", str(machine), *GIT, "-c", "protocol.file.allow=always", "submodule", "add", "-q",
                    str(remotes / "stoq.git"), "modules/stoq"], check=True, capture_output=True)
    (machine / ".gitignore").write_text(".fabriq/\n", encoding="utf-8")
    _init_with_remote(machine, remotes / "machine.git")
    # A fake gh on PATH.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "fake_gh.py").write_text(FAKE_GH, encoding="utf-8")
    if sys.platform == "win32":
        (bin_dir / "gh.cmd").write_text(f'@"{sys.executable}" "{bin_dir / "fake_gh.py"}" %*\n', encoding="utf-8")
    else:
        script = bin_dir / "gh"
        script.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{bin_dir / "fake_gh.py"}" "$@"\n', encoding="utf-8")
        script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("FAKE_GH_STORE", str(tmp_path / "gh.json"))
    return {"machine": machine, "public": public, "private": private, "remotes": remotes, "store": tmp_path / "gh.json"}


def test_text_follows_the_reporting_rule():
    report = {"command": "add-part", "root": "/x", "written": ["a", "b"], "edited": ["c"], "unchanged": [],
              "warnings": ["w"], "errors": [], "next_steps": ["Build the wrapper", "Open the pull requests"],
              "facts": {"pn": "HGL15", "brand": "hiwin"}}
    message = reporting.commit_message([report], "We need the block for the carriage.")
    first = message.splitlines()[0]
    assert first == "feat(hiwin): HGL15 recorded in the parts library"
    assert len(first) <= 72
    assert "We need the block" in message
    title = reporting.pr_title([report])
    assert title == "HGL15 recorded in the parts library"
    body = reporting.pr_body([report], "We need the block for the carriage.", checks="doqs check passed.")
    assert reporting.check_body(body) == []
    head = body.split("<details>")[0]
    assert "## What changed" in head and "## How it was checked" in head
    assert "Build the wrapper" in head and "Open the pull requests" not in head
    assert "- `a`" in body and "- w" in body
    assert reporting.clip("x" * 100) .endswith("…") and len(reporting.clip("word " * 30)) <= 72
    assert reporting.check_body("## What changed\n\n" + "word " * 250 + "<details>")
    assert slugify("Add the HGL15 block!") == "add-the-hgl15-block"


def test_a_change_set_commits_in_order_opens_prs_and_bumps_the_pin_after_the_merge(repos, stub_env):
    machine, public, private = repos["machine"], repos["public"], repos["private"]
    workspace = open_workspace(machine)
    api = load_doqs(workspace.doqs_scripts)
    assert [n for n, _, _ in ChangeSets(workspace).repositories()] == ["stoq-private", "stoq", "machine"]
    # Changes in all three repositories, with reports for two of them.
    report = api.intake(private=private, public=public, brand="hiwin", family="hgl-block", pn="HGL15",
                        description="Block", decision="customers", reviewer="N. B.", validate=False)
    assert report.ok, report.errors
    use = api.use_part(machine, Path("modules/linear-guide-x"), "stoq:hiwin/hgr-rail#HGR20R500")
    assert use.ok, use.errors
    reports = {str(private.resolve()): [json.loads(report.to_json())], str(machine.resolve()): [json.loads(use.to_json())]}
    sets = ChangeSets(workspace)
    cs = sets.create("add the HGL15 block", "The carriage needs it.", reports)
    assert [r.name for r in cs.repos] == ["stoq-private", "stoq", "machine"]
    assert all(r.branch == "feat/add-the-hgl15-block" for r in cs.repos)
    assert cs.repos[0].commit_message.startswith("feat(hiwin): HGL15 recorded in the parts library")
    assert cs.repos[2].commit_message.startswith("feat(")
    assert "## What changed" in cs.repos[1].pr_body
    sets.update_text(cs, "stoq", pr_title="Record the HGL15 block")
    with pytest.raises(ValueError):
        sets.update_text(cs, "stoq", pr_body="no headings here")

    # A stray edit inside the mounted library blocks the machine commit.
    stray = machine / "modules" / "stoq" / "library.toml"
    original = stray.read_text(encoding="utf-8")
    stray.write_text(original + "# touched\n", encoding="utf-8")
    with pytest.raises(RuntimeError) as err:
        sets.commit(cs)
    assert "modules/stoq/library.toml" in str(err.value)
    stray.write_text(original, encoding="utf-8")

    cs = sets.commit(cs)
    assert cs.state == "committed"
    for repo in cs.repos:
        assert repo.commit, repo.notes
        assert git(Path(repo.path), "rev-parse", "--abbrev-ref", "HEAD") == "feat/add-the-hgl15-block"
        assert git(Path(repo.path), "status", "--porcelain") == ""
    assert git(public, "log", "-1", "--format=%s") == "feat(hiwin): HGL15 recorded in the parts library"

    cs = sets.push_and_pr(cs)
    assert cs.state == "pushed"
    assert [r.pr_url for r in cs.repos] == ["https://github.example/org/repo/pull/1", "https://github.example/org/repo/pull/2",
                                             "https://github.example/org/repo/pull/3"]
    store = json.loads(repos["store"].read_text())
    assert store[cs.repos[1].pr_url]["title"] == "Record the HGL15 block"
    assert "Related pull requests" in store[cs.repos[2].pr_url]["body"]
    assert git(public, "rev-parse", "origin/feat/add-the-hgl15-block") == cs.repos[1].commit

    # GitHub merges the library pull requests: merge into main in a clone and push.
    for name, repo in (("stoq", cs.repos[1]), ("stoq-private", cs.repos[0])):
        clone = repos["remotes"].parent / f"merge-{name}"
        subprocess.run(["git", "clone", "-q", str(repos["remotes"] / f"{name}.git"), str(clone)], check=True, capture_output=True)
        git(clone, "merge", "-q", "--no-ff", "-m", "Merge pull request", f"origin/{repo.branch}")
        git(clone, "push", "-q", "origin", "main")
        merge_sha = git(clone, "rev-parse", "HEAD")
        store = json.loads(repos["store"].read_text())
        store[repo.pr_url].update({"state": "MERGED", "merge": merge_sha})
        repos["store"].write_text(json.dumps(store))
    cs = sets.refresh(cs)
    assert cs.repos[1].pr_state == "MERGED" and cs.repos[0].pr_state == "MERGED"
    cs = sets.bump_after_merge(cs, api, poll=0.01, timeout=10)
    assert cs.state == "done"
    assert cs.repos[1].pin_bumped == cs.repos[1].merge_commit
    assert git(machine / "modules" / "stoq", "rev-parse", "HEAD") == cs.repos[1].merge_commit
    assert git(machine, "diff", "--cached", "--name-only") == "modules/stoq"
    # The pin bump staged a change: the next change set carries it to the machine.
    again = sets.create("use the merged library", "", {})
    assert [r.name for r in again.repos] == ["machine"]
    assert again.repos[0].commit_message.startswith("chore(machine)")
