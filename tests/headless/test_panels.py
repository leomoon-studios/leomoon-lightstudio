"""Headless verification: every Step 14 panel + UIList class is registered.

Run with::

    blender --background --factory-startup \
        --python tests/headless/test_panels.py
"""

from __future__ import annotations

import sys

import addon_utils
import bpy

ADDON_ID = "bl_ext.user_default.leomoon_lightstudio"

EXPECTED_PANELS = (
    "LLS_PT_studio",
    "LLS_PT_mode",
    "LLS_PT_profile_list",
    "LLS_PT_lights",
    "LLS_PT_selected",
    "LLS_PT_background",
    "LLS_PT_profile_import_export",
    "LLS_PT_misc",
    "LLS_PT_hotkeys",
)

EXPECTED_UILISTS = (
    "LLS_UL_ProfileList",
    "LLS_UL_LightList",
)


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    if addon_utils.enable(ADDON_ID, default_set=False, persistent=False) is None:
        fail(f"could not enable {ADDON_ID}")

    # Panel & UIList classes register their bl_idname on bpy.types.
    for bl_idname in EXPECTED_PANELS + EXPECTED_UILISTS:
        if not hasattr(bpy.types, bl_idname):
            fail(f"missing class {bl_idname}")
    print(
        f"registered: {len(EXPECTED_PANELS)} panels + "
        f"{len(EXPECTED_UILISTS)} UILists"
    )

    # Preferences class is registered but AddonPreferences are not
    # exposed on bpy.types under their class name — confirm via the
    # package module instead.
    from bl_ext.user_default.leomoon_lightstudio.ui import preferences

    if preferences.LLSPreferences.bl_idname != ADDON_ID:
        fail(
            f"LLSPreferences.bl_idname = {preferences.LLSPreferences.bl_idname!r}, "
            f"expected {ADDON_ID!r}"
        )
    print(f"preferences class registered: bl_idname={preferences.LLSPreferences.bl_idname}")

    addon_utils.disable(ADDON_ID, default_set=False)
    for bl_idname in EXPECTED_PANELS + EXPECTED_UILISTS:
        if hasattr(bpy.types, bl_idname):
            fail(f"{bl_idname} still registered after disable")
    print("PASS: panels + UILists register and unregister cleanly")


if __name__ == "__main__":
    main()
