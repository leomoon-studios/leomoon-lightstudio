"""Resolve the LightStudio light currently targeted by selection-aware UI."""

from __future__ import annotations

import bpy

from . import light_linking
from .scene_utils import family

_pin_retarget_timer_pending = False


def _tag_lightstudio_ui_redraw() -> None:
    wm = bpy.context.window_manager
    if wm is None:
        return
    for window in wm.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            area.tag_redraw()
            for region in area.regions:
                if region.type == "UI":
                    region.tag_redraw()


def active_light_handle(context: bpy.types.Context) -> bpy.types.Object | None:
    """Return the active object's LightStudio handle, if the active object is a light."""
    handle = light_linking.resolve_light_handle(context.active_object)
    if handle is None or not light_linking.is_valid_lightstudio_light(handle):
        return None
    return handle


def selected_light_handle(
    context: bpy.types.Context,
) -> bpy.types.Object | None:
    """Return the handle the Selected Light UI should display.

    Active LightStudio selections always win. If a light is pinned and a
    regular Blender object is selected, the pinned LightStudio light remains
    the UI target. This function is read-only so it is safe to call from
    panel drawing and enum callbacks.
    """
    props = getattr(context.scene, "LLStudio", None)
    if getattr(props, "pin_selected_light", False):
        pinned_name = getattr(props, "pinned_light_handle_name", "")
        pinned_handle = bpy.data.objects.get(pinned_name)
        if (
            pinned_handle is not None
            and light_linking.is_valid_lightstudio_light(pinned_handle)
        ):
            return pinned_handle

    return active_light_handle(context)


def _apply_pin_retarget() -> None:
    global _pin_retarget_timer_pending
    _pin_retarget_timer_pending = False
    context = bpy.context
    props = getattr(context.scene, "LLStudio", None)
    if not getattr(props, "pin_selected_light", False):
        return
    active_handle = active_light_handle(context)
    if active_handle is not None:
        if props.pinned_light_handle_name != active_handle.name:
            props.pinned_light_handle_name = active_handle.name
            _tag_lightstudio_ui_redraw()
        return
    pinned_handle = bpy.data.objects.get(getattr(props, "pinned_light_handle_name", ""))
    if pinned_handle is None or not light_linking.is_valid_lightstudio_light(pinned_handle):
        props.pin_selected_light = False
        props.pinned_light_handle_name = ""
        _tag_lightstudio_ui_redraw()


def _pin_retarget_timer() -> None:
    _apply_pin_retarget()
    return None


def retarget_pin_to_active_light(context: bpy.types.Context, *, immediate: bool = False) -> None:
    """If pinning is enabled, retarget it to the active LightStudio light."""
    global _pin_retarget_timer_pending
    props = getattr(context.scene, "LLStudio", None)
    if not getattr(props, "pin_selected_light", False):
        return
    if immediate:
        _apply_pin_retarget()
        return
    if _pin_retarget_timer_pending:
        return
    _pin_retarget_timer_pending = True
    try:
        bpy.app.timers.register(_pin_retarget_timer, first_interval=0)
    except ValueError:
        _pin_retarget_timer_pending = False


def light_mesh_from_handle(handle: bpy.types.Object | None) -> bpy.types.Object | None:
    """Return the advanced mesh child for ``handle``."""
    if handle is None:
        return None
    for child in family(handle):
        if child.name.startswith("LLS_LIGHT_MESH"):
            return child
    return None


def light_object_for_handle(handle: bpy.types.Object | None) -> bpy.types.Object | None:
    """Return the Basic/Advanced child currently represented by ``handle``."""
    if handle is None:
        return None
    prefix = "LLS_LIGHT_AREA" if handle.LLStudio.type == "BASIC" else "LLS_LIGHT_MESH"
    for child in family(handle):
        if child.name.startswith(prefix):
            return child
    return None
