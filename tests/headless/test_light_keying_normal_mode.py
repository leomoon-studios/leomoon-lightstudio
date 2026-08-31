"""Headless test: selected LightStudio lights key in normal mode."""

from __future__ import annotations

import contextlib
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
    _quit(1)


def _quit(code: int) -> None:
    with contextlib.suppress(Exception):
        bpy.ops.wm.quit_blender()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


def _enable_addon():
    addon_utils.disable(EXTENSION_MODULE, default_set=False)
    module = addon_utils.enable(EXTENSION_MODULE, default_set=False)
    registered_locally = False
    if module is None:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        module = importlib.import_module("lightstudio")
        module.register()
        registered_locally = True
    return module, registered_locally


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


def _has_action(obj: bpy.types.Object) -> bool:
    return bool(obj.animation_data and obj.animation_data.action)


def _action_data_paths(obj: bpy.types.Object) -> set[str]:
    action = obj.animation_data.action
    fcurves = getattr(action, "fcurves", None)
    if fcurves is not None:
        return {fcurve.data_path for fcurve in fcurves}

    paths: set[str] = set()
    slots = tuple(getattr(action, "slots", ()) or ())
    for layer in getattr(action, "layers", ()) or ():
        for strip in getattr(layer, "strips", ()) or ():
            channelbags = getattr(strip, "channelbags", None)
            if channelbags is not None:
                for bag in channelbags:
                    paths.update(fcurve.data_path for fcurve in bag.fcurves)
                continue
            channelbag = getattr(strip, "channelbag", None)
            if not callable(channelbag):
                continue
            for slot in slots:
                with contextlib.suppress(Exception):
                    bag = channelbag(slot)
                    if bag is not None:
                        paths.update(fcurve.data_path for fcurve in bag.fcurves)
    return paths


def _advanced_intensity_socket(obj: bpy.types.Object):
    return obj.active_material.node_tree.nodes["Group"].inputs["Intensity"]


def main() -> None:
    module, registered_locally = _enable_addon()
    light_linking = importlib.import_module(f"{module.__name__}.core.light_linking")
    app_handlers = importlib.import_module(f"{module.__name__}.handlers.app_handlers")

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
    actuator = handle.parent
    basic_area, advanced_mesh = light_linking.resolve_light_emitters(handle)
    if basic_area is None or advanced_mesh is None:
        _fail("light has incomplete Basic/Advanced emitters")

    _select_object(advanced_mesh)

    scene.frame_set(1)
    handle.location.z = 10.0
    handle.rotation_euler.y = 0.2
    handle.scale = (1.25, 1.0, 1.5)
    if actuator is not None:
        actuator.rotation_euler.x = 0.1
        actuator.rotation_euler.y = -0.15
    with bpy.context.temp_override(**override):
        result = bpy.ops.lls.insert_key_active_light()
    if result != {"FINISHED"}:
        _fail(f"insert_key_active_light frame 1 returned {result!r}")

    scene.frame_set(12)
    handle.location.z = 40.0
    handle.rotation_euler.y = 0.7
    handle.scale = (2.0, 1.0, 2.5)
    if actuator is not None:
        actuator.rotation_euler.x = 0.4
        actuator.rotation_euler.y = 0.35
    with bpy.context.temp_override(**override):
        result = bpy.ops.lls.insert_key_active_light()
    if result != {"FINISHED"}:
        _fail(f"insert_key_active_light frame 12 returned {result!r}")

    if _has_action(handle):
        _fail("keying should not create an action on the hidden light handle")
    if actuator is not None and _has_action(actuator):
        _fail("keying should not create an action on the hidden light actuator")

    expected_transform_paths = {
        "LLStudio.anim_distance",
        "LLStudio.anim_position_x",
        "LLStudio.anim_position_y",
        "LLStudio.anim_rotation",
        "LLStudio.anim_scale_x",
        "LLStudio.anim_scale_y",
        "LLStudio.anim_scale_z",
    }
    for emitter in (basic_area, advanced_mesh):
        if not _has_action(emitter):
            _fail(f"{emitter.name} should own visible LightStudio keys")
        paths = _action_data_paths(emitter)
        if paths != expected_transform_paths:
            _fail(
                f"{emitter.name} keyed paths {sorted(paths)}, "
                f"expected only {sorted(expected_transform_paths)}"
            )
    if basic_area.animation_data.action != advanced_mesh.animation_data.action:
        _fail("basic and advanced emitters should share one action")
    if (
        basic_area.animation_data.action_slot_handle
        != advanced_mesh.animation_data.action_slot_handle
    ):
        _fail("basic and advanced emitters should share one action slot")

    scene.frame_set(1)
    app_handlers._lls_update_frame(scene)
    scene.frame_set(12)
    app_handlers._lls_update_frame(scene)
    if abs(handle.location.z - 40.0) > 0.001:
        _fail(f"handle distance did not follow visible emitter keys: {handle.location.z}")
    if abs(handle.rotation_euler.y - 0.7) > 0.001:
        _fail("handle rotation did not follow visible emitter keys")
    if actuator is not None and abs(actuator.rotation_euler.x - 0.4) > 0.001:
        _fail("actuator X rotation did not follow visible emitter keys")

    scene.frame_set(20)
    advanced_mesh.LLStudio.adv_intensity = 7.0
    advanced_mesh.keyframe_insert(data_path="LLStudio.adv_intensity", frame=20)
    paths = _action_data_paths(advanced_mesh)
    if "LLStudio.adv_intensity" not in paths:
        _fail("advanced option key did not land on selected visible light object")
    if "LLStudio.adv_intensity" not in _action_data_paths(basic_area):
        _fail("advanced option key should appear through the shared basic action")
    app_handlers._lls_update_frame(scene)
    if abs(float(_advanced_intensity_socket(advanced_mesh).default_value) - 7.0) > 0.001:
        _fail("advanced option key did not drive the material socket")

    addon_utils.disable(EXTENSION_MODULE, default_set=False)
    if registered_locally:
        module.unregister()

    print("PASS: normal-mode keying uses visible light objects for transform and options")
    _quit(0)


if __name__ == "__main__":
    main()
