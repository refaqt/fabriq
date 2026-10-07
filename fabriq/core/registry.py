"""Modules plug into the shell here.

A module is a Python package with a ``register(app)`` function that returns
a ``ModuleManifest``: a name, a title, the navigation entries the shell
shows, and the API router to mount under ``/api/<name>``. Modules are found
through the ``fabriq.modules`` entry-point group, so a later module
(worqflows, faqtory, maqe, produqts, qommunity) is a new package and nothing
in the shell changes. The built-in ``doqs`` module is always there.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import Callable

from fastapi import APIRouter


@dataclass
class NavItem:
    label: str
    path: str
    icon: str = "circle"


@dataclass
class ModuleManifest:
    name: str
    title: str
    nav: list[NavItem] = field(default_factory=list)
    router: APIRouter | None = None
    ui_entry: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.name, "title": self.title, "ui_entry": self.ui_entry or self.name,
            "nav": [{"label": n.label, "path": n.path, "icon": n.icon} for n in self.nav],
        }


Registrar = Callable[["object"], ModuleManifest]


def discover() -> dict[str, Registrar]:
    """``{name: register}`` for every installed module, built-ins first."""
    from fabriq.modules import doqs as doqs_module

    found: dict[str, Registrar] = {"doqs": doqs_module.register}
    try:
        for ep in entry_points(group="fabriq.modules"):
            if ep.name in found:
                continue
            try:
                found[ep.name] = ep.load()
            except Exception:  # noqa: BLE001 - a broken plug-in must not stop the shell
                continue
    except Exception:  # noqa: BLE001
        pass
    return found
