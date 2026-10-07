"""``fabriq``: find the workspace, start the server, open the browser."""
from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

from fabriq import __version__
from fabriq.core.workspace import WorkspaceError, open_workspace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fabriq", description="The design tool for DOQS repositories.")
    parser.add_argument("--root", type=Path, default=None, help="Machine or library repository root")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--version", action="version", version=f"fabriq {__version__}")
    args = parser.parse_args(argv)
    try:
        workspace = open_workspace(args.root)
    except WorkspaceError as exc:
        print(f"fabriq: {exc}", file=sys.stderr)
        return 2
    settings = workspace.settings
    host = args.host or settings.host
    port = args.port or settings.port
    import uvicorn

    from fabriq.app import create_app

    app = create_app(workspace)
    state = app.state.fabriq
    print(f"fabriq {__version__}: {workspace.kind} {workspace.name} at {workspace.root}")
    if state.doqs_error:
        print(f"WARN  {state.doqs_error}")
    url = f"http://{host}:{port}/"
    print(f"      {url}")
    if settings.open_browser and not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
