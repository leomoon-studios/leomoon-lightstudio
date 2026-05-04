"""Headless smoke test: profile CRUD + export/import round-trip.

Creates 2 profiles, adds lights to each, exports profile A to a temp
``.lls`` file, deletes that profile, re-imports the file, and asserts
that every light's name and key transform attributes match the
original.

Invoke directly::

    blender --background --factory-startup \\
        --python tests/headless/test_profiles_io.py
"""

from __future__ import annotations

import os
import sys
import tempfile

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


def _light_signature(handle_name: str) -> tuple:
    handle = bpy.data.objects[handle_name]
    return (
        handle.LLStudio.light_name,
        round(handle.location.z, 5),
        round(handle.rotation_euler.y, 5),
        tuple(round(v, 5) for v in handle.scale),
        handle.LLStudio.type,
    )


def main() -> None:
    addon_utils.disable(EXTENSION_MODULE, default_set=False)
    if addon_utils.enable(EXTENSION_MODULE, default_set=False) is None:
        _fail(f"could not enable {EXTENSION_MODULE}")

    scene = bpy.context.scene
    override = _override_view3d(bpy.context)
    if override is None:
        _fail("no VIEW_3D area")

    # 1. Create studio (auto-seeds Profile 1).
    with bpy.context.temp_override(**override):
        if bpy.ops.scene.create_leomoon_light_studio() != {"FINISHED"}:
            _fail("create studio failed")

    props = scene.LLStudio
    if len(props.profile_list) != 1:
        _fail(f"expected 1 profile after create, got {len(props.profile_list)}")

    # 2. Rename Profile 1 -> "Studio A" and add 2 lights.
    props.profile_list[0].name = "Studio A"
    for _ in range(2):
        with bpy.context.temp_override(**override):
            if bpy.ops.scene.add_leomoon_studio_light() != {"FINISHED"}:
                _fail("add light to A failed")

    # Tweak transforms so we can verify round-trip.
    a_handles = [li.handle_name for li in props.light_list]
    bpy.data.objects[a_handles[0]].location.z = 7.5
    bpy.data.objects[a_handles[0]].rotation_euler.y = 0.42
    bpy.data.objects[a_handles[0]].LLStudio.light_name = "Key"
    bpy.data.objects[a_handles[1]].LLStudio.light_name = "Fill"

    a_signatures = [_light_signature(n) for n in a_handles]
    a_count = len(a_handles)

    # 3. Add a second profile + one light so the index pointer matters.
    with bpy.context.temp_override(**override):
        if bpy.ops.lls_list.new_profile() != {"FINISHED"}:
            _fail("new_profile B failed")
    props.profile_list[-1].name = "Studio B"
    with bpy.context.temp_override(**override):
        if bpy.ops.scene.add_leomoon_studio_light() != {"FINISHED"}:
            _fail("add light to B failed")
    if len(props.profile_list) != 2:
        _fail(f"expected 2 profiles, got {len(props.profile_list)}")

    # 4. Export profile A.
    props.profile_list_index = 0
    tmpdir = tempfile.mkdtemp(prefix="lls_test_")
    export_path = os.path.join(tmpdir, "studio_a.lls")
    with bpy.context.temp_override(**override):
        if bpy.ops.lls_list.export_profiles(filepath=export_path) != {"FINISHED"}:
            _fail("export_profiles failed")
    if not os.path.isfile(export_path) or os.path.getsize(export_path) == 0:
        _fail(f"export file missing or empty: {export_path}")

    # 5. Delete profile A.
    props.profile_list_index = 0
    with bpy.context.temp_override(**override):
        if bpy.ops.lls_list.delete_profile() != {"FINISHED"}:
            _fail("delete_profile A failed")
    if len(props.profile_list) != 1:
        _fail(f"expected 1 profile after delete, got {len(props.profile_list)}")
    if props.profile_list[0].name != "Studio B":
        _fail(f"expected 'Studio B' to remain, got {props.profile_list[0].name!r}")

    # 6. Re-import profile A.
    with bpy.context.temp_override(**override):
        if bpy.ops.lls_list.import_profiles(filepath=export_path) != {"FINISHED"}:
            _fail("import_profiles failed")

    # The import operator appends a fresh profile at the end of the list.
    if len(props.profile_list) != 2:
        _fail(f"expected 2 profiles after import, got {len(props.profile_list)}")

    imported_idx = next(
        (i for i, p in enumerate(props.profile_list) if "Studio A" in p.name),
        None,
    )
    if imported_idx is None:
        _fail(
            "imported profile name did not contain 'Studio A': "
            f"{[p.name for p in props.profile_list]}"
        )

    props.profile_list_index = imported_idx
    # Force a refresh so light_list reflects the imported profile.
    with bpy.context.temp_override(**override):
        bpy.ops.light_studio.refresh_lightlist()

    if len(props.light_list) != a_count:
        _fail(
            f"expected {a_count} lights after re-import, got {len(props.light_list)}"
        )

    imported_signatures = [_light_signature(li.handle_name) for li in props.light_list]
    # Order is sorted by order_index in export, so compare sets.
    if sorted(imported_signatures) != sorted(a_signatures):
        _fail(
            "light signatures changed after round-trip:\n"
            f"  before: {sorted(a_signatures)}\n"
            f"  after : {sorted(imported_signatures)}"
        )

    print("PASS: profile CRUD + export/import round-trip clean")


if __name__ == "__main__":
    main()
