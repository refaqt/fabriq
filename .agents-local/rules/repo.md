# fabriq: repository rules

fabriq is the shell: a FastAPI backend, a React frontend, a job runner, FreeCAD sessions, git
and GitHub. The design rules live in doqs. See [docs/architecture.md](../../docs/architecture.md).

- fabriq never writes a design rule. A function that changes a file in a machine or library
  repository belongs in doqs (`scripts/<verb>_<object>.py`). fabriq calls it through
  `doqs_api` and shows the report.
- One fabriq process serves one workspace (a machine repository or a library). The doqs it
  uses is the one the workspace pins at `doqs/`.
- Long work (FreeCAD, `doqs check`, git push) runs as a job. A request returns a job id; the
  browser follows it over the event stream. Nothing long runs inside a request.
- Only one FreeCAD job runs at a time.
- Commit types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ui`, `api`.

## Checks before a pull request

```bash
uv run pytest
uv run python -m compileall -q fabriq
cd frontend && npm ci && npm run build && npm test
```
