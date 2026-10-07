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

## Next Steps

- The frontend shell in Refaqt's colours, the parts library browser, the add-part wizard and
  the job drawer.
- The git layer: change sets across the three repositories, generated commit and pull
  request text, pin bumps after a merge.
