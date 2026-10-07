# ADR-001 — fabriq is a shell; the rules stay in doqs

- **Date:** 2026-10-07
- **Status:** Accepted

Write this file in B2 English. Follow `.agents/rules/communication.md`. Keep official names, file paths, and numbers exact.

## Context

Adding a part to a machine took days of hand work across three repositories. The fix has
two halves: commands that do the work the same way every time, and a tool that makes them
easy to use from a browser. AI agents must get the same result as a person who clicks.

Two ways were open. Put the logic in the tool, and let agents call the tool's API. Or put
the logic in doqs, the tools-and-specification repository every machine already mounts, and
make the tool a thin layer over it.

## Decision

- Every rule that changes a repository lives in doqs, as a command with `--json` and
  `--dry-run`. fabriq imports doqs from the workspace's own `doqs/scripts/` folder, so the
  pinned version is the one used, and checks `doqs_api.API_VERSION` at start.
- fabriq is a platform shell. A module is a Python package that registers routes and a
  navigation entry (entry-point group `fabriq.modules`) and a frontend bundle. The design
  tool is the first module, `doqs`. Later modules (worqflows, faqtory, maqe, produqts,
  qommunity) use the same shell.
- Backend: Python 3.12 with FastAPI. Frontend: React with Tailwind and React Flow. Local
  first; a container later.
- One process serves one workspace. Long work runs as a job with progress over server-sent
  events. One FreeCAD job at a time.
- Branches a change set creates are `feat/<topic>`, the same name in every repository.
  Library changes always go through a library pull request; a machine's pin moves only to a
  merged commit.

## Consequences

- An agent without fabriq loses nothing: the doqs commands are the whole logic.
- doqs stays standard-library only, so machine repositories do not grow.
- fabriq's own tests use the doqs fixtures as workspaces; a change in doqs that changes a
  report shape shows up here first.
