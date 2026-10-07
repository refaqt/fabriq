# fabriq architecture

fabriq is a platform shell. A module plugs into it with a Python package that registers
API routes and a navigation entry, and a frontend bundle under `frontend/src/modules/<name>/`.
The first module is `doqs`, the design tool. This page is the short overview; the detail
lives next to the code.

## One rule

Every rule that changes a repository lives in doqs. fabriq imports doqs from the workspace's
own `doqs/scripts/` folder, through `doqs_api`, and checks its `API_VERSION` at start. fabriq
adds what a browser needs around those rules: a read model, jobs, events, FreeCAD sessions,
git and GitHub.

## Parts

| Part | Path | Does |
| --- | --- | --- |
| Command line | `fabriq/cli.py` | Finds the workspace root, starts the server, opens the browser |
| Settings | `fabriq/config.py` | `FABRIQ_*` environment variables and `<root>/.fabriq/local.toml` |
| Workspace | `fabriq/core/workspace.py` | The machine root, its kind, the mounted libraries and the sibling library checkouts |
| doqs bridge | `fabriq/core/doqs_bridge.py` | Imports `doqs_api` from the workspace, runs `doqs <command>` as a subprocess |
| Jobs | `fabriq/core/jobs.py` | Background work with steps and logs, persisted under `<root>/.fabriq/jobs/` |
| Events | `fabriq/core/events.py` | Server-sent events: `job.updated`, `model.changed`, `git.changed` |
| Registry | `fabriq/core/registry.py` | Finds modules through the `fabriq.modules` entry-point group |
| App | `fabriq/app.py` | The FastAPI application: core routes, module routes, the built frontend |
| doqs module | `fabriq/modules/doqs/` | The design tool: read model, library, parts, interfaces, checks |

## The doqs module

The read model (`readmodel.py`) is built from the files in the workspace: every `okh.toml`,
`bom/bom.csv`, `cad/params*.csv`, `architecture/*.sysml`, `builds/*/build.toml`, the saved
FreeCAD documents (trees, frames, joints, links, read without FreeCAD), and the library rows.
It is rebuilt when a file changes. Writes go through the doqs commands, as jobs, and the
report of each command is what the browser shows and what a commit message is made from.

## Jobs and FreeCAD

A request that starts long work returns a job id at once. The job runs in a thread or as a
subprocess, reports its steps over the event stream, and keeps its result on disk. Only one
FreeCAD job runs at a time. FreeCAD is reached the way doqs reaches it: the open window
through the RPC server, a window started for the job, or FreeCADCmd.
