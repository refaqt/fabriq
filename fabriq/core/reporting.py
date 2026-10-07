"""Commit messages and pull request text in the shape the agent kit asks for.

The text is made from the structured reports the doqs commands return, plus
the designer's own comment, never from the raw diff. The rules are those of
`.agents/rules/reporting.md`: a title of at most 72 characters that says
what a person can now do; four headings in a fixed order; everything above
the closed block under 200 words; the technical detail inside the block;
commit lines as ``type(scope): what changed, in plain words``.
"""
from __future__ import annotations

import textwrap

TITLE_MAX = 72
WORDS_MAX = 200
HEADINGS = ("## What changed", "## Why it matters", "## What you need to do", "## How it was checked")

#: How a doqs command reads in a sentence a manager understands.
COMMAND_WORDS = {
    "add-part": "recorded in the parts library",
    "wrap": "wrapped for FreeCAD with its colours and mounting frames",
    "use-part": "added to the bill of materials, the manifest and the architecture",
    "add-interface": "connected with a named interface in the architecture and a mounting frame in each part",
    "scaffold module": "created as a new module with every folder the rules expect",
    "scaffold part": "created as a new part with its build script and document",
    "scaffold brand": "created as a new brand in the parts library",
    "scaffold family": "created as a new family in the parts library",
}

COMMIT_TYPES = {
    "add-part": "feat", "wrap": "cad", "use-part": "feat", "add-interface": "interface",
    "scaffold module": "feat", "scaffold part": "cad", "scaffold brand": "feat", "scaffold family": "feat",
}


def _subject(report: dict) -> str:
    facts = report.get("facts") or {}
    for key in ("pn", "part", "port_def", "module", "family", "brand"):
        if facts.get(key):
            return str(facts[key])
    return ""


def _scope(report: dict, fallback: str) -> str:
    facts = report.get("facts") or {}
    for key in ("brand", "module", "family"):
        value = facts.get(key)
        if value:
            return str(value).split("/")[-1]
    return fallback


def one_line(report: dict) -> str:
    """One sentence for one report: ``HGL15CAZBC+E2 recorded in the parts library``."""
    command = report.get("command", "")
    words = COMMAND_WORDS.get(command, f"changed by {command}")
    subject = _subject(report)
    return f"{subject} {words}".strip() if subject else words[:1].upper() + words[1:]


def clip(text: str, limit: int = TITLE_MAX) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0]
    return cut + "…"


def commit_message(reports: list[dict], comment: str = "", scope: str = "", commit_types: tuple[str, ...] = ()) -> str:
    """``type(scope): what changed`` plus a short body saying why."""
    if not reports:
        first = f"chore({scope}): record the changes" if scope else "chore: record the changes"
        return clip(first) + (f"\n\n{comment.strip()}\n" if comment.strip() else "\n")
    main = reports[0]
    kind = COMMIT_TYPES.get(main.get("command", ""), "feat")
    if commit_types and kind not in commit_types:
        kind = "feat" if "feat" in commit_types else commit_types[0]
    scope = scope or _scope(main, "design")
    lines = [one_line(r) for r in reports]
    first = clip(f"{kind}({scope}): {lines[0][:1].lower() + lines[0][1:]}")
    body = []
    if comment.strip():
        body.append(comment.strip())
    if len(lines) > 1:
        body.append("Also: " + "; ".join(lines[1:]) + ".")
    return first + ("\n\n" + "\n\n".join(textwrap.fill(b, 72) for b in body) + "\n" if body else "\n")


def pr_title(reports: list[dict], topic: str = "") -> str:
    if reports:
        return clip(one_line(reports[0])[:1].upper() + one_line(reports[0])[1:])
    return clip(topic.replace("-", " ").capitalize() or "Record the changes")


def _words(text: str) -> int:
    return len(text.split())


def pr_body(reports: list[dict], comment: str = "", checks: str = "", files: list[str] | None = None,
            related: list[str] | None = None) -> str:
    """The four headings and the closed block, under 200 words above the block."""
    changed = [one_line(r) for r in reports]
    what = ". ".join(c[:1].upper() + c[1:] for c in changed) + "." if changed else "Files in this repository changed; see the notes."
    why = comment.strip() or "This is part of adding a part to the design with the fabriq design tool."
    todo = []
    for r in reports:
        todo += [s for s in r.get("next_steps", []) if "pull request" not in s.lower()]
    todo_text = " ".join(dict.fromkeys(todo)) if todo else "Nothing."
    checked = checks.strip() or "Not checked yet: run `doqs check` on this branch."
    warnings = [w for r in reports for w in r.get("warnings", [])]
    notes = []
    for r in reports:
        notes.append(f"- `{r.get('command')}`: wrote {len(r.get('written', []))} files, changed {len(r.get('edited', []))}.")
        for path in (r.get("written", []) + r.get("edited", []))[:40]:
            notes.append(f"  - `{path}`")
    if files:
        notes.append("- Files in this commit:")
        notes += [f"  - `{f}`" for f in files[:60]]
    if warnings:
        notes.append("- Warnings from the commands:")
        notes += [f"  - {w}" for w in warnings]
    if related:
        notes.append("- Related: " + ", ".join(related))
    top = (
        f"{HEADINGS[0]}\n\n{what}\n\n{HEADINGS[1]}\n\n{why}\n\n{HEADINGS[2]}\n\n{todo_text}\n\n"
        f"{HEADINGS[3]}\n\n{checked}\n"
    )
    if _words(top) > WORDS_MAX:
        top = (
            f"{HEADINGS[0]}\n\n{clip(what, 400)}\n\n{HEADINGS[1]}\n\n{clip(why, 300)}\n\n"
            f"{HEADINGS[2]}\n\n{clip(todo_text, 200)}\n\n{HEADINGS[3]}\n\n{clip(checked, 200)}\n"
        )
    block = "\n<details>\n<summary>Notes for reviewers</summary>\n\n" + "\n".join(notes) + "\n\n</details>\n"
    return top + block


def check_body(body: str) -> list[str]:
    """Why a body does not follow the rule; empty when it does."""
    problems = []
    head = body.split("<details>", 1)[0]
    for heading in HEADINGS:
        if heading not in head:
            problems.append(f"missing heading {heading}")
    if _words(head) > WORDS_MAX:
        problems.append(f"{_words(head)} words above the notes, the limit is {WORDS_MAX}")
    return problems
