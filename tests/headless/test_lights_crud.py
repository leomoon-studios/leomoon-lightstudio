"""Headless smoke test: light add / copy / move / mute / isolate.

Bootstraps a studio (using the step-11 ``seed_first_profile`` helper to
stand in for the step-12 profile-CRUD operator), adds 3 lights, copies
one, moves it down, then exercises mute + isolate, asserting the
``light_list`` ordering and mute flags.

Invoke directly::

    blender --background --factory-startup \\
        --python tests/headless/test_lights_crud.py
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


def _assert_new_light_unlinked(handle: bpy.types.Object, light_linking) -> None:
    props = handle.LLStudio
    bucket_names = (
        "light_linking_include_targets",
        "light_linking_exclude_targets",
        "shadow_linking_include_targets",
        "shadow_linking_exclude_targets",
    )
    for name in bucket_names:
        if len(getattr(props, name)) != 0:
            _fail(f"new light {handle.name} has non-empty {name}")
    basic_area, advanced_mesh = light_linking.resolve_light_emitters(handle)
    for emitter in (basic_area, advanced_mesh):
        if emitter is None:
            _fail(f"new light {handle.name} has incomplete emitter hierarchy")
        if emitter.light_linking.receiver_collection is not None:
            _fail(f"new light {handle.name} receiver collection should be None")
        if emitter.light_linking.blocker_collection is not None:
            _fail(f"new light {handle.name} blocker collection should be None")


def _state_for_object(
    collection: bpy.types.Collection,
    obj: bpy.types.Object,
) -> str | None:
    index = collection.objects.find(obj.name)
    if index < 0:
        return None
    return collection.collection_objects[index].light_linking.link_state


def _state_for_collection(
    collection: bpy.types.Collection,
    child: bpy.types.Collection,
) -> str | None:
    index = collection.children.find(child.name)
    if index < 0:
        return None
    return collection.collection_children[index].light_linking.link_state


def _child_collection(
    light_handle: bpy.types.Object,
    prefix: str,
) -> bpy.types.Collection:
    for child in light_handle.children:
        if child.users_collection and child.users_collection[0].name.startswith(prefix):
            return child.users_collection[0]
    _fail(f"{light_handle.name} has no {prefix} child collection")


def _assert_light_type_visibility(
    context: bpy.types.Context,
    light_handle: bpy.types.Object,
    scene_utils,
) -> None:
    basic = _child_collection(light_handle, "LLS_Basic")
    advanced = _child_collection(light_handle, "LLS_Advanced")
    basic_view = scene_utils.find_view_layer(basic, context.view_layer.layer_collection)
    advanced_view = scene_utils.find_view_layer(
        advanced,
        context.view_layer.layer_collection,
    )
    if basic_view is None or advanced_view is None:
        _fail("missing Basic/Advanced layer collection")

    expected = (
        (True, False)
        if light_handle.LLStudio.type == "ADVANCED"
        else (False, True)
    )
    actual = (basic_view.exclude, advanced_view.exclude)
    if actual != expected:
        _fail(
            f"{light_handle.name} Basic/Advanced excludes are {actual}, "
            f"expected {expected}"
        )


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

    light_linking = importlib.import_module(f"{module.__name__}.core.light_linking")
    scene_utils = importlib.import_module(f"{module.__name__}.core.scene_utils")

    scene = bpy.context.scene
    override = _override_view3d(bpy.context)
    if override is None:
        _fail("no VIEW_3D area")

    # 1. Create studio (auto-seeds the first profile via lls_list.new_profile).
    with bpy.context.temp_override(**override):
        if bpy.ops.scene.create_leomoon_light_studio() != {"FINISHED"}:
            _fail("create studio failed")

    # 2. Add the first light and verify one-light isolate preserves
    # Basic/Advanced child visibility.
    with bpy.context.temp_override(**override):
        result = bpy.ops.scene.add_leomoon_studio_light()
    if result != {"FINISHED"}:
        _fail(f"add light #0 returned {result!r}")
    first_handle = bpy.data.objects[scene.LLStudio.light_list[0].handle_name]
    first_handle.LLStudio.type = "ADVANCED"
    scene_utils.sync_light_type_visibility(first_handle, bpy.context)
    with bpy.context.temp_override(**override):
        if bpy.ops.light_studio.isolate(index=0) != {"FINISHED"}:
            _fail("one-light isolate failed")
    _assert_light_type_visibility(bpy.context, first_handle, scene_utils)

    # Add 2 more lights for the rest of the CRUD coverage.
    for i in range(1, 3):
        with bpy.context.temp_override(**override):
            result = bpy.ops.scene.add_leomoon_studio_light()
        if result != {"FINISHED"}:
            _fail(f"add light #{i} returned {result!r}")

    if len(scene.LLStudio.light_list) != 3:
        _fail(
            f"expected 3 lights in light_list, got {len(scene.LLStudio.light_list)}"
        )
    for item in scene.LLStudio.light_list:
        _assert_new_light_unlinked(bpy.data.objects[item.handle_name], light_linking)

    # 3. Copy the second light. The copy should land directly after it.
    scene.LLStudio.light_list_index = 1
    second_handle_name = scene.LLStudio.light_list[1].handle_name
    second_handle = bpy.data.objects[second_handle_name]
    receiver = bpy.data.objects.new("Light Linking Receiver", None)
    bpy.context.scene.collection.objects.link(receiver)
    blocker_collection = bpy.data.collections.new("Shadow Linking Blockers")
    bpy.context.scene.collection.children.link(blocker_collection)
    light_linking.add_light_linking_target_row(
        second_handle,
        "LIGHT",
        "INCLUDE",
        receiver,
    )
    light_linking.add_light_linking_target_row(
        second_handle,
        "SHADOW",
        "EXCLUDE",
        blocker_collection,
    )
    source_area, source_mesh = light_linking.resolve_light_emitters(second_handle)
    source_receiver_wrapper = source_area.light_linking.receiver_collection
    source_blocker_wrapper = source_mesh.light_linking.blocker_collection
    if source_receiver_wrapper is None or source_blocker_wrapper is None:
        _fail("source light linking wrappers were not assigned before copy")
    # Activate a child of the handle (the operator copies based on context.object.parent).
    visible = [c for c in second_handle.children if c.visible_get()]
    if not visible:
        _fail("active light handle has no visible child")
    bpy.context.view_layer.objects.active = visible[0]
    visible[0].select_set(True)

    with bpy.context.temp_override(**override):
        if bpy.ops.lls_list.copy_light() != {"FINISHED"}:
            _fail("copy_light failed")

    if len(scene.LLStudio.light_list) != 4:
        _fail(f"expected 4 lights after copy, got {len(scene.LLStudio.light_list)}")
    copy_names = [li.name for li in scene.LLStudio.light_list]
    if not any(n.endswith("Copy") for n in copy_names):
        _fail(f"no '... Copy' entry in light_list: {copy_names}")
    copied_handle = bpy.data.objects[scene.LLStudio.light_list[2].handle_name]
    if len(copied_handle.LLStudio.light_linking_include_targets) != 1:
        _fail("copied light did not copy Light Linking Include rows")
    if len(copied_handle.LLStudio.shadow_linking_exclude_targets) != 1:
        _fail("copied light did not copy Shadow Linking Exclude rows")
    if copied_handle.LLStudio.light_linking_include_targets[0].object_target != receiver:
        _fail("copied Light Linking row does not point at the same receiver object")
    if (
        copied_handle.LLStudio.shadow_linking_exclude_targets[0].collection_target
        != blocker_collection
    ):
        _fail("copied Shadow Linking row does not point at the same blocker collection")
    copied_area, copied_mesh = light_linking.resolve_light_emitters(copied_handle)
    copied_receiver_wrapper = copied_area.light_linking.receiver_collection
    copied_blocker_wrapper = copied_mesh.light_linking.blocker_collection
    if copied_receiver_wrapper is None or copied_blocker_wrapper is None:
        _fail("copied light native wrappers were not assigned")
    if copied_receiver_wrapper == source_receiver_wrapper:
        _fail("copied light reused source receiver wrapper")
    if copied_blocker_wrapper == source_blocker_wrapper:
        _fail("copied light reused source blocker wrapper")
    if _state_for_object(copied_receiver_wrapper, receiver) != "INCLUDE":
        _fail("copied receiver row did not preserve INCLUDE mode")
    if _state_for_collection(copied_blocker_wrapper, blocker_collection) != "EXCLUDE":
        _fail("copied shadow row did not preserve EXCLUDE mode")

    # 4. Move the last light up by one (DOWN of index 0 → swaps with index 1).
    scene.LLStudio.light_list_index = 0
    with bpy.context.temp_override(**override):
        if bpy.ops.lls_list.move_light(direction="DOWN") != {"FINISHED"}:
            _fail("move_light DOWN failed")
    moved_names = [li.name for li in scene.LLStudio.light_list]
    # Soft check: ordering should differ from the post-copy snapshot.
    if moved_names == copy_names:
        _fail(f"move_light DOWN had no effect: {moved_names}")

    # 5. Mute the first light.
    scene.LLStudio.light_list_index = 0
    with bpy.context.temp_override(**override):
        if bpy.ops.light_studio.mute_toggle(index=0) != {"FINISHED"}:
            _fail("mute_toggle failed")
    if not scene.LLStudio.light_list[0].mute:
        _fail("light 0 not muted after mute_toggle")

    # Unmute it again.
    with bpy.context.temp_override(**override):
        bpy.ops.light_studio.mute_toggle(index=0)
    if scene.LLStudio.light_list[0].mute:
        _fail("light 0 still muted after second mute_toggle")

    # 6. Isolate the second light: every other entry must end up muted.
    with bpy.context.temp_override(**override):
        if bpy.ops.light_studio.isolate(index=1) != {"FINISHED"}:
            _fail("isolate failed")
    for i, li in enumerate(scene.LLStudio.light_list):
        expected = i != 1
        if li.mute != expected:
            _fail(
                f"after isolate, light {i}.mute = {li.mute}, expected {expected}"
            )

    # Re-isolate same light → restores everyone.
    with bpy.context.temp_override(**override):
        bpy.ops.light_studio.isolate(index=1)
    if any(li.mute for li in scene.LLStudio.light_list):
        muted = [(i, li.mute) for i, li in enumerate(scene.LLStudio.light_list)]
        _fail(f"after isolate-restore, lights still muted: {muted}")

    # 7. Camera-toggle one light off and on.
    start_visible_camera = scene.LLStudio.light_list[1].visible_camera
    with bpy.context.temp_override(**override):
        if bpy.ops.light_studio.camera_toggle(index=1) != {"FINISHED"}:
            _fail("camera_toggle failed")
    if scene.LLStudio.light_list[1].visible_camera == start_visible_camera:
        _fail("light 1 camera visibility did not change after camera_toggle")

    with bpy.context.temp_override(**override):
        if bpy.ops.light_studio.camera_toggle(index=1) != {"FINISHED"}:
            _fail("second camera_toggle failed")
    if scene.LLStudio.light_list[1].visible_camera != start_visible_camera:
        _fail("light 1 camera visibility did not restore after second camera_toggle")

    # 8. Camera-toggle all lights off.
    with bpy.context.temp_override(**override):
        if bpy.ops.lls.camera_toggle_all_lights(visible_camera=False) != {"FINISHED"}:
            _fail("camera_toggle_all_lights failed")

    if registered_locally:
        module.unregister()
    else:
        addon_utils.disable(EXTENSION_MODULE, default_set=False)
    print("PASS: lights add/copy/move/mute/isolate clean")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
