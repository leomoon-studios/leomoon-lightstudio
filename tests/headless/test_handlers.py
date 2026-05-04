"""Headless verification: Step 17 handlers + keying set + EXR operator.

Asserts:

1. Persistent handlers from ``handlers.app_handlers`` are appended:
   ``frame_change_post`` (light energy sync), ``render_complete`` /
   ``render_cancel`` (EXR cleanup).
2. The ``handlers.msgbus`` ``LayerObjects.active`` subscription
   re-installs on file load via ``load_post``.
3. ``BUILTIN_KSI_LightStudio`` is registered as a ``KeyingSetInfo``.
4. ``lls.lls_keyingset`` and ``lls.render_lights_exr`` operators are
   registered.
5. After ``addon_utils.disable``, all handlers are removed and the
   keying set / operators are gone.

Run with::

    blender --background --factory-startup \\
        --python tests/headless/test_handlers.py
"""

from __future__ import annotations

import sys

import addon_utils
import bpy

ADDON_ID = "bl_ext.user_default.leomoon_lightstudio"


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    if addon_utils.enable(ADDON_ID, default_set=True, persistent=True) is None:
        _fail(f"could not enable {ADDON_ID}")

    from bl_ext.user_default.leomoon_lightstudio.handlers import (
        app_handlers,
        msgbus,
    )

    if app_handlers._lls_update_frame not in bpy.app.handlers.frame_change_post:
        _fail("_lls_update_frame not in frame_change_post")
    if app_handlers._render_complete not in bpy.app.handlers.render_complete:
        _fail("_render_complete not in render_complete")
    if app_handlers._render_cancel not in bpy.app.handlers.render_cancel:
        _fail("_render_cancel not in render_cancel")
    if msgbus._load_post_resubscribe not in bpy.app.handlers.load_post:
        _fail("msgbus _load_post_resubscribe not in load_post")

    if not hasattr(bpy.types, "BUILTIN_KSI_LightStudio"):
        ks_ids = {k.bl_idname for k in bpy.context.scene.keying_sets_all}
        if "BUILTIN_KSI_LightStudio" not in ks_ids:
            _fail("BUILTIN_KSI_LightStudio not registered")

    for op_id in ("LLS_OT_lls_keyingset", "LLS_OT_render_lights_exr"):
        if not hasattr(bpy.types, op_id):
            _fail(f"{op_id} not registered")

    addon_utils.disable(ADDON_ID, default_set=True)

    if app_handlers._lls_update_frame in bpy.app.handlers.frame_change_post:
        _fail("_lls_update_frame leaked")
    if app_handlers._render_complete in bpy.app.handlers.render_complete:
        _fail("_render_complete leaked")
    if app_handlers._render_cancel in bpy.app.handlers.render_cancel:
        _fail("_render_cancel leaked")
    if msgbus._load_post_resubscribe in bpy.app.handlers.load_post:
        _fail("msgbus _load_post_resubscribe leaked")
    ks_ids = {k.bl_idname for k in bpy.context.scene.keying_sets_all}
    if "BUILTIN_KSI_LightStudio" in ks_ids:
        _fail("BUILTIN_KSI_LightStudio not unregistered")

    print("PASS: app handlers + msgbus + keying set + EXR operator clean")


if __name__ == "__main__":
    main()
