"""Settings: environment variables ``FABRIQ_*`` and ``<root>/.fabriq/local.toml``.

The local file is per workspace and never committed (it is in the
workspace's ``.gitignore`` through fabriq's first run). It holds what differs
per machine: where the library checkouts are, which FreeCAD to start.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

LOCAL_DIR = ".fabriq"
LOCAL_FILE = "local.toml"


@dataclass
class Settings:
    host: str = "127.0.0.1"
    port: int = 8765
    open_browser: bool = True
    #: Library checkouts beside the machine, by library name: {"stoq": {"public": ..., "private": ...}}.
    libraries: dict[str, dict[str, str]] = field(default_factory=dict)
    freecad: str | None = None
    freecad_mode: str = "auto"
    rpc_url: str = "http://127.0.0.1:9875"
    github_user: str = ""
    #: Take the Git LFS lock on a FreeCAD file as soon as it changes.
    lfs_locks: bool = True

    @classmethod
    def load(cls, root: Path | None = None) -> "Settings":
        settings = cls()
        if root is not None:
            local = root / LOCAL_DIR / LOCAL_FILE
            if local.is_file():
                try:
                    data = tomllib.loads(local.read_text(encoding="utf-8"))
                except tomllib.TOMLDecodeError:
                    data = {}
                server = data.get("server", {})
                settings.host = str(server.get("host", settings.host))
                settings.port = int(server.get("port", settings.port))
                settings.open_browser = bool(server.get("open_browser", settings.open_browser))
                libs = data.get("libraries", {})
                if isinstance(libs, dict):
                    settings.libraries = {
                        str(name): {str(k): str(v) for k, v in paths.items()}
                        for name, paths in libs.items() if isinstance(paths, dict)
                    }
                freecad = data.get("freecad", {})
                settings.freecad = freecad.get("binary") or None
                settings.freecad_mode = str(freecad.get("mode", settings.freecad_mode))
                settings.rpc_url = str(freecad.get("rpc_url", settings.rpc_url))
                settings.github_user = str(data.get("github", {}).get("user", ""))
                settings.lfs_locks = bool(data.get("git", {}).get("lfs_locks", settings.lfs_locks))
        env = os.environ
        settings.host = env.get("FABRIQ_HOST", settings.host)
        settings.port = int(env.get("FABRIQ_PORT", settings.port))
        if env.get("FABRIQ_NO_BROWSER"):
            settings.open_browser = False
        settings.freecad = env.get("FABRIQ_FREECAD", settings.freecad)
        settings.freecad_mode = env.get("FABRIQ_FREECAD_MODE", settings.freecad_mode)
        settings.rpc_url = env.get("FABRIQ_RPC_URL", settings.rpc_url)
        if env.get("FABRIQ_LFS_LOCKS") is not None:
            settings.lfs_locks = env["FABRIQ_LFS_LOCKS"] not in ("0", "false", "no", "")
        return settings
