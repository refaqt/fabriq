# 2026-10-07 — fabriq starts: the shell and the doqs module

**Role(s):** software

## What happened

fabriq begins. The six doqs commands that add a part to a design exist (see
[refaqt/doqs#45](https://github.com/refaqt/doqs/pull/45)). fabriq wraps them for a browser.

Work done:

- The repository skeleton, with the shared agent kit, the licence, the docs folders and CI.
- The backend core: settings, workspace discovery, the bridge that imports doqs from the
  workspace, the job runner with persisted jobs, the event stream, the module registry, the
  FastAPI app factory and the `fabriq` command.
- The doqs module: a read model of the design built from the files in the workspace, and the
  routes that start the doqs commands as jobs.

## Decisions

- [ADR-001 — fabriq is a shell; the rules stay in doqs](../decisions/2026-10-07_shell-and-rules.md)

- The frontend shell in Refaqt's colours: the workspace page with the state of each
  repository and FreeCAD, the modules page with a block diagram of each module read from its
  SysML, the parts library browser with the add-part wizard and the wrap action, and a job
  drawer with live progress.
- The git layer: a change set creates the branch `feat/<topic>` in each repository, commits
  in the order private library, public library, machine, opens the pull requests, and moves
  the machine's pins after the library pull requests merge. Commit messages and pull request
  text come from the command reports plus the designer's comment, in the shape the agent kit
  asks for, and can be edited before use.

## Checked

- The backend tests run the whole chain on the doqs fixtures with the fake FreeCAD, and the
  change-set flow against real git repositories with bare remotes and a fake `gh`.
- fabriq ran on a trimmed copy of the aqtuator repository: the home page, the compact stage's
  block diagram with its eight connections and the parts library with both brands rendered in
  Refaqt's colours.

## Next Steps

- Run the chain by hand on the real repositories once: add a part, wrap it, use it, connect
  it, open the pull requests.
- Diagram editing, requirements editing, versions and builds, the container for online use.
