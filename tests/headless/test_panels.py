"""Headless verification: every Step 14 panel + UIList class is registered.

Run with::

    blender --background --factory-startup \
        --python tests/headless/test_panels.py
"""

from __future__ import annotations

import contextlib
import importlib
import os
import sys
from pathlib import Path

import addon_utils
import bpy

ADDON_ID = "bl_ext.user_default.leomoon_lightstudio"
ROOT = Path(__file__).resolve().parents[2]

EXPECTED_PANELS = (
    "LLS_PT_studio",
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
    _quit(1)


def _quit(code: int) -> None:
    with contextlib.suppress(Exception):
        bpy.ops.wm.quit_blender()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


def main() -> None:
    addon_utils.disable(ADDON_ID, default_set=False)
    module = addon_utils.enable(ADDON_ID, default_set=False, persistent=False)
    registered_locally = False
    if module is None:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        module = importlib.import_module("lightstudio")
        module.register()
        module.ui.panels.register()
        registered_locally = True

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
    preferences = importlib.import_module(f"{module.__name__}.ui.preferences")

    expected_addon_id = module.__name__ if registered_locally else ADDON_ID
    if preferences.LLSPreferences.bl_idname != expected_addon_id:
        fail(
            f"LLSPreferences.bl_idname = {preferences.LLSPreferences.bl_idname!r}, "
            f"expected {expected_addon_id!r}"
        )
    print(f"preferences class registered: bl_idname={preferences.LLSPreferences.bl_idname}")

    addon_utils.disable(ADDON_ID, default_set=False)
    if registered_locally:
        module.unregister()
    for bl_idname in EXPECTED_PANELS + EXPECTED_UILISTS:
        if hasattr(bpy.types, bl_idname):
            fail(f"{bl_idname} still registered after disable")
    print("PASS: panels + UILists register and unregister cleanly")
    _quit(0)


if __name__ == "__main__":
    main()
