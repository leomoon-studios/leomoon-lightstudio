"""Operator registration for LeoMoon LightStudio.

Filled incrementally in steps 10-17 (studio lifecycle, light CRUD,
profiles, textures, modal control panel, light brush, EXR export).
"""

from __future__ import annotations

import contextlib

import bpy

from . import (  # noqa: F401
    delete,
    exr_export,
    light,
    light_brush,
    modal,
    profiles,
    studio,
    textures,
)


def register() -> None:
    for cls in studio.classes:
        bpy.utils.register_class(cls)
    for cls in light.classes:
        bpy.utils.register_class(cls)
    for cls in profiles.classes:
        bpy.utils.register_class(cls)
    for cls in textures.classes:
        bpy.utils.register_class(cls)
    for cls in light_brush.classes:
        bpy.utils.register_class(cls)
    for cls in delete.classes:
        bpy.utils.register_class(cls)
    for cls in exr_export.classes:
        bpy.utils.register_class(cls)
    modal.register()
    profiles.register_handlers()


def unregister() -> None:
    profiles.unregister_handlers()
    modal.unregister()
    for module in (exr_export, delete, light_brush, textures, profiles, light, studio):
        for cls in reversed(module.classes):
            with contextlib.suppress(RuntimeError, ValueError):
                bpy.utils.unregister_class(cls)
