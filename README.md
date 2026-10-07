# fabriq

fabriq is the platform around Refaqt's open hardware. Its first module is the **DOQS design
tool**: a local web app that adds a part to a machine design in minutes. Later modules
(worqflows, faqtory, maqe, produqts, qommunity) plug into the same shell.

fabriq does not hold design rules of its own. Every rule that changes a repository lives in
[doqs](https://github.com/refaqt/doqs), as commands an agent can also call directly. fabriq
is the shell around them: a browser interface, background jobs, FreeCAD sessions, git and
GitHub.

## Run it

From a machine repository that mounts doqs at `doqs/`:

```bash
uv tool install fabriq      # once; pipx works too
fabriq                      # finds the repository root, starts the server, opens the browser
```

You also need [Git LFS](https://git-lfs.com) (`git lfs install`). fabriq uses it to lock a
FreeCAD file while you change it, so a colleague does not change the same file at the same
time. Set `FABRIQ_LFS_LOCKS=0`, or `lfs_locks = false` under `[git]` in
`.fabriq/local.toml`, to turn the locks off.

For development:

```bash
git clone --recurse-submodules https://github.com/refaqt/fabriq.git
cd fabriq
uv sync --extra dev
uv run fabriq --root ../aqtuator
uv run pytest
```

## Documentation

| Doc | Purpose |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | How the shell, the doqs module, jobs, FreeCAD and git fit together |
| [docs/decisions/](docs/decisions/) | Why choices were made |
| [docs/log/](docs/log/) | What was done, by date |
| [docs/mistakes/](docs/mistakes/) | What went wrong, and the rule that prevents it |
| [AGENTS.md](AGENTS.md) | Start here if you are an agent changing this repository |

## Licence

fabriq is software: [GPL-3.0-or-later](LICENSE). The documentation under `docs/` is
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The REFAQT and DOQS names
and logos are trademarks and are not covered by these licences.
