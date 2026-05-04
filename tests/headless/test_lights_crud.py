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

import sys

import addon_utils
import bpy

EXTENSION_MODULE = "bl_ext.user_default.leomoon_lightstudio"


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def _override_view3d(context: bpy.types.Context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                return {"window": window, "screen": window.screen, "area": area}
    return None


def main() -> None:
    addon_utils.disable(EXTENSION_MODULE, default_set=False)
    if addon_utils.enable(EXTENSION_MODULE, default_set=False) is None:
        _fail(f"could not enable {EXTENSION_MODULE}")

    scene = bpy.context.scene
    override = _override_view3d(bpy.context)
    if override is None:
        _fail("no VIEW_3D area")

    # 1. Create studio (auto-seeds the first profile via lls_list.new_profile).
    with bpy.context.temp_override(**override):
        if bpy.ops.scene.create_leomoon_light_studio() != {"FINISHED"}:
            _fail("create studio failed")

    # 2. Add 3 lights.
    for i in range(3):
        with bpy.context.temp_override(**override):
            result = bpy.ops.scene.add_leomoon_studio_light()
        if result != {"FINISHED"}:
            _fail(f"add light #{i} returned {result!r}")

    if len(scene.LLStudio.light_list) != 3:
        _fail(
            f"expected 3 lights in light_list, got {len(scene.LLStudio.light_list)}"
        )

    # 3. Copy the second light. The copy should land directly after it.
    scene.LLStudio.light_list_index = 1
    second_handle_name = scene.LLStudio.light_list[1].handle_name
    second_handle = bpy.data.objects[second_handle_name]
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

    # 7. Camera-toggle off.
    with bpy.context.temp_override(**override):
        if bpy.ops.lls.camera_toggle_all_lights(visible_camera=False) != {"FINISHED"}:
            _fail("camera_toggle_all_lights failed")

    addon_utils.disable(EXTENSION_MODULE, default_set=False)
    print("PASS: lights add/copy/move/mute/isolate clean")


if __name__ == "__main__":
    main()
