"""Headless regression test: binary mask switches are integer 0/1 values."""

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


def _light_mesh(handle: bpy.types.Object) -> bpy.types.Object:
    for child in handle.children:
        if child.name.startswith("LLS_LIGHT_MESH"):
            return child
    _fail(f"{handle.name} has no advanced light mesh")


def _group_inputs(light_mesh: bpy.types.Object):
    return light_mesh.active_material.node_tree.nodes["Group"].inputs


def _assert_mask_float_clamps(mesh: bpy.types.Object, inputs) -> None:
    mask_props = {
        "adv_mask_gradient_type": "Mask - Gradient Type",
        "adv_mask_gradient_amount": "Mask - Gradient Amount",
        "adv_mask_ring_inner_radius": "Mask - Ring Inner Radius",
        "adv_mask_ring_outer_radius": "Mask - Ring Outer Radius",
        "adv_mask_top_to_bottom": "Mask - Top to Bottom",
        "adv_mask_bottom_to_top": "Mask - Bottom to Top",
        "adv_mask_left_to_right": "Mask - Left to Right",
        "adv_mask_right_to_left": "Mask - Right to Left",
        "adv_mask_diagonal_top_left": "Mask - Diagonal Top Left",
        "adv_mask_diagonal_top_right": "Mask - Diagonal Top Right",
        "adv_mask_diagonal_bottom_right": "Mask - Diagonal Bottom Right",
        "adv_mask_diagonal_bottom_left": "Mask - Diagonal Bottom Left",
    }

    for prop_name, socket_name in mask_props.items():
        setattr(mesh.LLStudio, prop_name, 2.0)
        if getattr(mesh.LLStudio, prop_name) != 1.0:
            _fail(f"{socket_name} property did not clamp above 1.0")
        if inputs[socket_name].default_value != 1.0:
            _fail(f"{socket_name} socket did not receive clamped 1.0")

        setattr(mesh.LLStudio, prop_name, -1.0)
        if getattr(mesh.LLStudio, prop_name) != 0.0:
            _fail(f"{socket_name} property did not clamp below 0.0")
        if inputs[socket_name].default_value != 0.0:
            _fail(f"{socket_name} socket did not receive clamped 0.0")


def _parent_collection(child: bpy.types.Collection) -> bpy.types.Collection:
    for collection in bpy.data.collections:
        if collection.children.find(child.name) >= 0:
            return collection
    _fail(f"{child.name} has no parent collection")


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

    light_io = importlib.import_module(f"{module.__name__}.core.light_io")

    scene = bpy.context.scene
    override = _override_view3d(bpy.context)
    if override is None:
        _fail("no VIEW_3D area")

    with bpy.context.temp_override(**override):
        if bpy.ops.scene.create_leomoon_light_studio() != {"FINISHED"}:
            _fail("create studio failed")
        if bpy.ops.scene.add_leomoon_studio_light() != {"FINISHED"}:
            _fail("add light failed")

    handle = bpy.data.objects[scene.LLStudio.light_list[0].handle_name]
    mesh = _light_mesh(handle)
    inputs = _group_inputs(mesh)
    light_collection = handle.users_collection[0]
    profile_collection = _parent_collection(light_collection)

    inputs["Mask - Gradient Switch"].default_value = 0.25
    inputs["Mask - Ring Switch"].default_value = 2.0
    inputs["Mask - Backface"].default_value = 0.5
    if mesh.LLStudio.mask_gradient_switch != 1:
        _fail("gradient switch getter did not clamp old positive float to 1")
    if mesh.LLStudio.mask_ring_switch != 1:
        _fail("ring switch getter did not clamp old positive float to 1")
    if mesh.LLStudio.mask_backface != 1:
        _fail("backface getter did not clamp old positive float to 1")

    mesh.LLStudio.mask_gradient_switch = 0
    mesh.LLStudio.mask_ring_switch = 1
    mesh.LLStudio.mask_backface = 0
    if inputs["Mask - Gradient Switch"].default_value != 0:
        _fail("gradient switch setter did not write 0")
    if inputs["Mask - Ring Switch"].default_value != 1:
        _fail("ring switch setter did not write 1")
    if inputs["Mask - Backface"].default_value != 0:
        _fail("backface setter did not write 0")

    _assert_mask_float_clamps(mesh, inputs)

    exported = light_io.salvage_data(light_collection)
    if exported["advanced"]["Mask - Gradient Switch"] != 0:
        _fail("export did not keep gradient switch as integer 0")
    if exported["advanced"]["Mask - Ring Switch"] != 1:
        _fail("export did not keep ring switch as integer 1")
    if exported["advanced"]["Mask - Backface"] != 0:
        _fail("export did not keep backface as integer 0")

    import_payload = exported.to_dict()
    import_payload["advanced"]["Mask - Gradient Switch"] = 0.2
    import_payload["advanced"]["Mask - Ring Switch"] = 3.0
    import_payload["advanced"]["Mask - Backface"] = 0.75
    before_handles = {
        item.handle_name
        for item in scene.LLStudio.light_list
    }
    light_io.light_from_dict(import_payload, profile_collection)
    after_handles = {
        item.handle_name
        for item in scene.LLStudio.light_list
    }
    new_handle_names = after_handles - before_handles
    if len(new_handle_names) != 1:
        _fail("import did not add exactly one new light")
    imported_handle = bpy.data.objects[new_handle_names.pop()]
    imported_inputs = _group_inputs(_light_mesh(imported_handle))
    if imported_inputs["Mask - Gradient Switch"].default_value != 1:
        _fail("import did not clamp old gradient float to 1")
    if imported_inputs["Mask - Ring Switch"].default_value != 1:
        _fail("import did not clamp old ring float to 1")
    if imported_inputs["Mask - Backface"].default_value != 1:
        _fail("import did not clamp old backface float to 1")

    if registered_locally:
        module.unregister()
    else:
        addon_utils.disable(EXTENSION_MODULE, default_set=False)
    print("PASS: mask switches are binary integer inputs")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
