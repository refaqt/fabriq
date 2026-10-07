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
| Git | `fabriq/core/git.py` | Status, branches, commits and pushes through the `git` binary |
| LFS locks | `fabriq/core/lfs.py` | Takes, lists and releases Git LFS file locks through the `git lfs` binary |
| Lock keeper | `fabriq/core/locks.py` | Locks a FreeCAD file as soon as it changes, warns when a colleague holds it, keeps the state in `<root>/.fabriq/locks.json` |
| GitHub | `fabriq/core/github.py` | Pull requests through the `gh` command line, which carries the person's login |
| Reporting | `fabriq/core/reporting.py` | Commit messages and pull request text in the shape of `.agents/rules/reporting.md`, made from the command reports |
| Change sets | `fabriq/core/changesets.py` | One change across the repositories: branch, commit, pull request and pin bump, in the order private library, public library, machine |
| App | `fabriq/app.py` | The FastAPI application: core routes, module routes, the built frontend |
| doqs module | `fabriq/modules/doqs/` | The design tool: read model, library, parts, interfaces, checks |

## The doqs module

The read model (`readmodel.py`) is built from the files in the workspace: every `okh.toml`,
`bom/bom.csv`, `cad/params*.csv`, `architecture/*.sysml`, `builds/*/build.toml`, the saved
FreeCAD documents (trees, frames, joints, links, read without FreeCAD), and the library rows.
It is rebuilt when a file changes. Writes go through the doqs commands, as jobs, and the
report of each command is what the browser shows and what a commit message is made from.

## Change sets

A change set is one change across the repositories it touches. It carries a topic, the
designer's comment, and one entry per repository with the files git sees as changed and the
reports of the commands that wrote there. From those reports it generates the commit message
and the pull request text (editable before use). It then creates the branch `feat/<topic>`
in each repository, commits in the order private library, public library, machine, pushes,
opens the pull requests through `gh`, and, after the library pull requests merge, moves the
machine's pins to the merge commits. A machine commit is refused while a mounted library has
local changes, and the panel names the files.

## Locks on FreeCAD files

Git cannot merge two versions of a `.FCStd` file, because the file is a zip. So only one
person may change it at a time. The lock keeper checks every 10 seconds, and after every job.
A FreeCAD file counts as changed when git sees it as changed on disk, or when the open FreeCAD
window has unsaved changes in it (read over the RPC port; the keeper only reads). The keeper
then takes the Git LFS lock. When a colleague already holds the lock, the keeper does not take
it, and the browser shows a red warning at once.

A change set remembers the locks of the files it commits. A push stops while a colleague holds
one of its files. The locks go when the pull request merges or closes. A lock also goes when
the change is thrown away: no unsaved changes, a clean file, and no commit to it that is not
on `origin/main`. A lock found on the server, or taken by hand, stays until the person
releases it on the Git page.

The `lockable` mark in `.gitattributes` makes the file read-only until someone locks it. That
line belongs to the machine and library repositories, so doqs writes it, not fabriq. fabriq
shows a warning when it is missing.

## Jobs and FreeCAD

A request that starts long work returns a job id at once. The job runs in a thread or as a
subprocess, reports its steps over the event stream, and keeps its result on disk. Only one
FreeCAD job runs at a time. FreeCAD is reached the way doqs reaches it: the open window
through the RPC server, a window started for the job, or FreeCADCmd.
