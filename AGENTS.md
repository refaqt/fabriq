# Working on fabriq — agent instructions

Start here if you are an agent changing this repository.

## First step (required)

Check the shared agent kit before you read its rules or skills. Run this from the repository
root:

```bash
ls .agents/rules/core.md
```

If the file is missing, fill the folder:

```bash
git submodule update --init --remote --checkout .agents
```

Then read `.agents/rules/core.md`, `.agents/rules/communication.md`,
`.agents/rules/living-docs.md` and `.agents/rules/reporting.md`. Write every reply and every
file in B2 English.

## This repository

fabriq is the shell: a FastAPI backend, a React frontend, a job runner, FreeCAD sessions, git
and GitHub. The design rules live in doqs. **Do not add a rule here that changes files in a
machine repository.** Add it to doqs as a command, then call it from here. See
[docs/architecture.md](docs/architecture.md).

| You are adding | It goes in |
| --- | --- |
| Why a choice was made | `docs/decisions/YYYY-MM-DD_topic.md` |
| A day's work write-up | `docs/log/YYYY-MM-DD_topic.md` |
| Something that went wrong | `docs/mistakes/YYYY-MM-DD_topic.md` |

Every task starts on a new branch off `main`. Commit messages and pull requests follow
`.agents/rules/reporting.md`.

## Checks before a pull request

```bash
uv run pytest
uv run python -m compileall -q fabriq
cd frontend && npm ci && npm run build && npm test
```
