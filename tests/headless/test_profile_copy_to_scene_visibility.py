"""Headless regression test: copied advanced profiles restore child visibility.

Invoke directly::

    blender --background --factory-startup \\
        --python tests/headless/test_profile_copy_to_scene_visibility.py
"""

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


def _child_collection(
    handle: bpy.types.Object,
    prefix: str,
) -> bpy.types.Collection:
    if not handle.users_collection:
        _fail(f"{handle.name} has no light collection")
    collection = next(
        (c for c in handle.users_collection[0].children if c.name.startswith(prefix)),
        None,
    )
    if collection is None:
        _fail(f"{handle.name} missing {prefix} collection")
    return collection


def _layer_exclude(
    scene_utils,
    collection: bpy.types.Collection,
) -> bool:
    layer = scene_utils.find_view_layer(
        collection,
        bpy.context.view_layer.layer_collection,
    )
    if layer is None:
        _fail(f"no layer collection for {collection.name}")
    return bool(layer.exclude)


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

    scene_utils = importlib.import_module(f"{module.__name__}.core.scene_utils")

    source_scene = bpy.context.scene
    source_scene.name = "Source Scene"
    source_scene.render.engine = "CYCLES"
    override = _override_view3d(bpy.context)
    if override is None:
        _fail("no VIEW_3D area")

    with bpy.context.temp_override(**override):
        if bpy.ops.scene.create_leomoon_light_studio() != {"FINISHED"}:
            _fail("create studio failed")
        if bpy.ops.scene.add_leomoon_studio_light() != {"FINISHED"}:
            _fail("add light failed")

    source_props = source_scene.LLStudio
    source_props.profile_list[0].name = "Advanced Profile"
    if len(source_props.light_list) != 1:
        _fail(f"expected one source light, got {len(source_props.light_list)}")
    source_handle = bpy.data.objects[source_props.light_list[0].handle_name]
    source_handle.LLStudio.type = "ADVANCED"
    scene_utils.sync_light_type_visibility(source_handle, bpy.context)

    target_scene = bpy.data.scenes.new("Target Scene")
    with bpy.context.temp_override(**override):
        result = bpy.ops.lls_list.copy_profile_to_scene(sceneprop=target_scene.name)
    if result != {"FINISHED"}:
        _fail(f"copy_profile_to_scene failed: {result}")
    if bpy.context.scene.name != target_scene.name:
        _fail(f"expected active scene {target_scene.name}, got {bpy.context.scene.name}")

    target_props = bpy.context.scene.LLStudio
    if len(target_props.light_list) != 1:
        _fail(f"expected one copied light, got {len(target_props.light_list)}")
    copied_handle = bpy.data.objects[target_props.light_list[0].handle_name]
    if copied_handle.LLStudio.type != "ADVANCED":
        _fail(f"expected copied light type ADVANCED, got {copied_handle.LLStudio.type}")

    basic = _child_collection(copied_handle, "LLS_Basic")
    advanced = _child_collection(copied_handle, "LLS_Advanced")
    if not _layer_exclude(scene_utils, basic):
        _fail("copied advanced light left the basic child visible")
    if _layer_exclude(scene_utils, advanced):
        _fail("copied advanced light hid the advanced child")

    if registered_locally:
        module.unregister()
    else:
        addon_utils.disable(EXTENSION_MODULE, default_set=False)
    print("PASS: copy profile to scene restores advanced light visibility")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
