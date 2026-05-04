"""Shared utilities for LightStudio side panels.

Centralizes the ``bl_category`` and the common poll predicate so every
panel can be defined as a thin subclass.
"""

from __future__ import annotations

import bpy

PANEL_CATEGORY = "LightStudio"
PANEL_SPACE = "VIEW_3D"
PANEL_REGION = "UI"


def in_object_mode(context: bpy.types.Context) -> bool:
    return (
        context.area is not None
        and context.area.type == PANEL_SPACE
        and context.mode == "OBJECT"
    )


def studio_initialized(context: bpy.types.Context) -> bool:
    return in_object_mode(context) and context.scene.LLStudio.initialized


def has_profile(context: bpy.types.Context) -> bool:
    return in_object_mode(context) and bool(
        len(context.scene.LLStudio.profile_list)
    )


def op_registered(class_name: str) -> bool:
    """``True`` when the operator/keyingset class is currently registered."""
    return hasattr(bpy.types, class_name)
