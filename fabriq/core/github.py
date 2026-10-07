"""GitHub through the ``gh`` command line, which carries the person's login."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class GitHubError(RuntimeError):
    pass


def gh_available() -> bool:
    return shutil.which("gh") is not None


def _gh(path: Path, *args: str, input_text: str | None = None) -> str:
    # Resolve through PATH ourselves: on Windows a bare "gh" would skip a
    # `gh.cmd` that stands earlier on PATH and find `gh.exe` instead.
    exe = shutil.which("gh")
    if exe is None:
        raise GitHubError("the gh command line is not installed or not on PATH")
    result = subprocess.run([exe, *args], cwd=path, capture_output=True, text=True, input=input_text, timeout=120)
    if result.returncode != 0:
        raise GitHubError(result.stderr.strip() or result.stdout.strip() or "gh failed")
    return result.stdout.strip()


def create_pr(path: Path, title: str, body: str, base: str = "main", head: str | None = None) -> str:
    """Open a pull request for the current branch; returns its URL."""
    args = ["pr", "create", "--base", base, "--title", title, "--body-file", "-"]
    if head:
        args += ["--head", head]
    out = _gh(path, *args, input_text=body)
    for token in out.split():
        if token.startswith("https://"):
            return token
    return out


def pr_state(path: Path, url: str) -> dict:
    """``{"state": "OPEN"|"MERGED"|"CLOSED", "merged": bool, "merge_commit": sha|None, "checks": ...}``."""
    out = _gh(path, "pr", "view", url, "--json", "state,mergedAt,mergeCommit,url,number,statusCheckRollup")
    data = json.loads(out)
    merge = data.get("mergeCommit") or {}
    rollup = data.get("statusCheckRollup") or []
    failing = [c.get("name") or c.get("context") for c in rollup
               if str(c.get("conclusion") or c.get("state") or "").upper() in ("FAILURE", "ERROR")]
    return {
        "state": data.get("state"), "merged": data.get("state") == "MERGED",
        "merge_commit": merge.get("oid") if isinstance(merge, dict) else None,
        "number": data.get("number"), "url": data.get("url", url),
        "checks_failing": failing, "checks_total": len(rollup),
    }
