"""The DOQS design tool, fabriq's first module."""
from __future__ import annotations

from fabriq.core.registry import ModuleManifest, NavItem


def register(app) -> ModuleManifest:
    from fabriq.modules.doqs.routers import build_router

    return ModuleManifest(
        name="doqs",
        title="Design",
        nav=[
            NavItem("Workspace", "/", "home"),
            NavItem("Modules", "/modules", "boxes"),
            NavItem("Parts library", "/library", "library"),
            NavItem("Git", "/git", "git-branch"),
        ],
        router=build_router(app),
    )
