# fabriq: repository rules

- fabriq never writes a design rule. A function that changes a file in a machine or library
  repository belongs in doqs (`scripts/<verb>_<object>.py`). fabriq calls it through
  `doqs_api` and shows the report.
- One fabriq process serves one workspace (a machine repository or a library). The doqs it
  uses is the one the workspace pins at `doqs/`.
- Long work (FreeCAD, `doqs check`, git push) runs as a job. A request returns a job id; the
  browser follows it over the event stream. Nothing long runs inside a request.
- Only one FreeCAD job runs at a time.
- Commit types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ui`, `api`.
