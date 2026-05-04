"""UI registration for LeoMoon LightStudio.

Registers in this order: preview list (texture enum), UILists, panels
(in display order), preferences. Step 16 will replace the
``preferences`` stub with the full keymap editor.
"""

from __future__ import annotations

import contextlib

import bpy

from . import lists, panels, preferences, preview_list


def register() -> None:
    preview_list.register()
    for cls in lists.classes:
        bpy.utils.register_class(cls)
    panels.register()
    for cls in preferences.classes:
        bpy.utils.register_class(cls)


def _register_without_panels() -> None:
    """Same as :func:`register` but skips ``panels.register()``.

    The top-level extension entry point defers panel registration to a
    one-shot timer so the 3D-View sidebar tab appears on first install
    without requiring the user to disable/enable the addon. See
    ``lightstudio/__init__.py``.
    """
    preview_list.register()
    for cls in lists.classes:
        bpy.utils.register_class(cls)
    for cls in preferences.classes:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(preferences.classes):
        with contextlib.suppress(RuntimeError, ValueError):
            bpy.utils.unregister_class(cls)
    panels.unregister()
    for cls in reversed(lists.classes):
        with contextlib.suppress(RuntimeError, ValueError):
            bpy.utils.unregister_class(cls)
    preview_list.unregister()
