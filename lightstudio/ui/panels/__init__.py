"""Side-panel ordering for LeoMoon LightStudio.

Each panel module exposes a ``classes`` tuple and is registered in the
order below — Blender renders panels in registration order within the
same category, so this list is the single source of truth for panel
ordering.
"""

from __future__ import annotations

import contextlib

import bpy

from . import (
    background,
    hotkeys,
    import_export,
    lights,
    misc,
    mode,
    profile_list,
    selected,
    studio,
)

_PANEL_MODULES = (
    studio,
    mode,
    profile_list,
    lights,
    selected,
    background,
    import_export,
    misc,
    hotkeys,
)


def register() -> None:
    for module in _PANEL_MODULES:
        for cls in module.classes:
            # Skip already-registered classes — the top-level extension
            # entry point may invoke us a second time via a one-shot
            # timer (see lightstudio/__init__.py) and Blender raises
            # ValueError on duplicate register_class calls.
            if hasattr(bpy.types, cls.__name__):
                continue
            bpy.utils.register_class(cls)


def unregister() -> None:
    for module in reversed(_PANEL_MODULES):
        for cls in reversed(module.classes):
            # class may not be registered (e.g. stale dev install)
            with contextlib.suppress(RuntimeError, ValueError):
                bpy.utils.unregister_class(cls)
