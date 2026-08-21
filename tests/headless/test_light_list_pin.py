"""Headless test: Lights-list pin keeps Selected Light focused."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import addon_utils
import bpy

EXTENSION_MODULE = "bl_ext.user_default.leomoon_lightstudio"
ROOT = Path(__file__).resolve().parents[2]


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def _override_view3d(context: bpy.types.Context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                return {"window": window, "screen": window.screen, "area": area}
    return None


def _select_object(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)


def _visible_child(handle: bpy.types.Object) -> bpy.types.Object:
    children = [child for child in handle.children if child.visible_get()]
    if not children:
        _fail(f"{handle.name} has no visible child")
    return children[0]


def main() -> None:
    registered_locally = False
    addon_utils.disable(EXTENSION_MODULE, default_set=False)
    module = addon_utils.enable(EXTENSION_MODULE, default_set=False)
    if module is None:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        module = importlib.import_module("lightstudio")
        module.register()
        registered_locally = True

    selected_light = importlib.import_module(f"{module.__name__}.core.selected_light")

    scene = bpy.context.scene
    override = _override_view3d(bpy.context)
    if override is None:
        _fail("no VIEW_3D area")

    with bpy.context.temp_override(**override):
        if bpy.ops.scene.create_leomoon_light_studio() != {"FINISHED"}:
            _fail("create studio failed")
        if bpy.ops.scene.add_leomoon_studio_light() != {"FINISHED"}:
            _fail("add first light failed")
        if bpy.ops.scene.add_leomoon_studio_light() != {"FINISHED"}:
            _fail("add second light failed")

    first_handle = bpy.data.objects[scene.LLStudio.light_list[0].handle_name]
    second_handle = bpy.data.objects[scene.LLStudio.light_list[1].handle_name]

    with bpy.context.temp_override(**override):
        if bpy.ops.light_studio.pin_light(index=0) != {"FINISHED"}:
            _fail("pin first light failed")
    if not scene.LLStudio.pin_selected_light:
        _fail("pin_selected_light was not enabled")
    if scene.LLStudio.pinned_light_handle_name != first_handle.name:
        _fail("first light was not stored as pinned")

    cube = bpy.data.objects.new("Regular Object", None)
    scene.collection.objects.link(cube)
    _select_object(cube)
    if selected_light.selected_light_handle(bpy.context) != first_handle:
        _fail("regular object selection did not keep pinned first light")

    with bpy.context.temp_override(**override):
        if bpy.ops.light_studio.isolate(index=1) != {"FINISHED"}:
            _fail("isolate second light while pinned failed")
    if scene.LLStudio.pinned_light_handle_name != first_handle.name:
        _fail("isolate row should not retarget the active pin")
    if not scene.LLStudio.light_list[0].mute:
        _fail("isolate did not mute the other light while a regular object was active")
    with bpy.context.temp_override(**override):
        if bpy.ops.light_studio.isolate(index=1) != {"FINISHED"}:
            _fail("restore isolate second light while pinned failed")
    if any(item.mute for item in scene.LLStudio.light_list):
        _fail("isolate restore left lights muted")

    _select_object(_visible_child(second_handle))
    selected_light.retarget_pin_to_active_light(bpy.context, immediate=True)
    if selected_light.selected_light_handle(bpy.context) != second_handle:
        _fail("active LightStudio light did not override pinned first light")
    if scene.LLStudio.pinned_light_handle_name != second_handle.name:
        _fail("pin was not retargeted to selected second light")

    with bpy.context.temp_override(**override):
        if bpy.ops.light_studio.pin_light(index=0) != {"FINISHED"}:
            _fail("pin first light while second light selected failed")
    if selected_light.selected_light_handle(bpy.context) != first_handle:
        _fail("pinning a row did not make that row the selected-light target")

    with bpy.context.temp_override(**override):
        result = bpy.ops.light_studio.add_light_linking_target_row(
            category="LIGHT",
            mode="INCLUDE",
            target_type="OBJECT",
        )
    if result != {"FINISHED"}:
        _fail("pinned light-linking add row was grayed out or failed")
    if len(first_handle.LLStudio.light_linking_include_targets) != 1:
        _fail("pinned light-linking row was not added to the pinned light")
    if len(second_handle.LLStudio.light_linking_include_targets) != 0:
        _fail("pinned light-linking row was added to the active light instead")

    with bpy.context.temp_override(**override):
        if bpy.ops.light_studio.pin_light(index=0) != {"FINISHED"}:
            _fail("unpin first light failed")
    if scene.LLStudio.pin_selected_light or scene.LLStudio.pinned_light_handle_name:
        _fail("clicking pinned row did not clear pin")

    if registered_locally:
        module.unregister()
    else:
        addon_utils.disable(EXTENSION_MODULE, default_set=False)
    print("PASS: light list pin keeps Selected Light focused")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
