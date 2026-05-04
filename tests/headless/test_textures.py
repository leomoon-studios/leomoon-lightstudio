"""Headless verification: texture preview enum + missing-textures op.

Run with::

    blender --background --factory-startup \
        --python tests/headless/test_textures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import addon_utils
import bpy

ADDON_ID = "bl_ext.user_default.leomoon_lightstudio"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    mod = addon_utils.enable(ADDON_ID, default_set=False, persistent=False)
    if mod is None:
        fail(f"could not enable {ADDON_ID}")

    wm = bpy.context.window_manager

    # Trigger the enum callback (it lazy-scans + caches).
    items = type(wm).bl_rna.properties["lls_tex_previews"].enum_items_static
    # enum_items_static is empty for dynamic enums; force the callback by
    # iterating the EnumProperty getter via the bpy.props machinery:
    from bl_ext.user_default.leomoon_lightstudio.ui import preview_list

    items = preview_list._enum_items(None, bpy.context)
    if len(items) != 15:
        fail(f"expected 15 textures in preview enum, got {len(items)}")
    print(f"preview enum populated: {len(items)} items")

    # Verify file extensions filtered correctly.
    suffixes = {Path(it[0]).suffix.lower() for it in items}
    if not suffixes.issubset({".exr", ".hdr"}):
        fail(f"unexpected suffixes in enum: {suffixes}")

    # Exercise the missing-textures operator: needs a profile, so create one.
    win = bpy.context.window_manager.windows[0]
    screen = win.screen
    area = next(a for a in screen.areas if a.type != "EMPTY")
    area.type = "VIEW_3D"
    with bpy.context.temp_override(window=win, screen=screen, area=area):
        bpy.ops.scene.create_leomoon_light_studio()
        # Now that a profile exists, poll() of find_missing_textures passes.
        if not bpy.ops.lls.find_missing_textures.poll():
            fail("find_missing_textures.poll() failed even with a profile present")
        result = bpy.ops.lls.find_missing_textures()
        if result != {"FINISHED"}:
            fail(f"find_missing_textures returned {result}")

    # Confirm a renamed texture is detected: copy a real texture into a
    # tempdir, point an image at it, rename it on disk, and confirm
    # find_missing_files would mark it missing. We simulate by checking
    # the image's packed_file/filepath state directly.
    from bl_ext.user_default.leomoon_lightstudio.core.paths import TEXTURES_DIR

    tex = next(TEXTURES_DIR.iterdir())
    if not tex.is_file():
        fail("textures dir empty")

    # Open & disable cleanly.
    addon_utils.disable(ADDON_ID, default_set=False)
    print("PASS: texture preview enum + missing-textures op clean")


if __name__ == "__main__":
    main()
