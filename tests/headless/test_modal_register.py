"""Headless verification: Step 15c modal operator + sub-operators register.

Asserts:

1. The five operator ``bl_idname``s register
   (``light_studio.control_panel``, ``light_studio.grab``,
   ``light_studio.scale``, ``light_studio.rotate``,
   ``light_studio.reset_control_panel``).
2. ``running_modals == 0`` and ``panel_global is None`` at rest.
3. ``close_control_panel()`` and ``multiprofile_conditions(context)``
   are callable as no-ops without a live modal.
4. The G/S/R Object Mode keymap entries are registered (and reverse
   on disable).
5. Disabling the addon leaves no leftover ``running_modals`` or
   ``frame_change_post`` / ``load_post`` handlers.

Run with::

    blender --background --factory-startup \\
        --python tests/headless/test_modal_register.py
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

    from bl_ext.user_default.leomoon_lightstudio.operators.modal import control_panel

    expected = {
        "LIGHT_STUDIO_OT_control_panel",
        "LIGHT_STUDIO_OT_grab",
        "LIGHT_STUDIO_OT_scale",
        "LIGHT_STUDIO_OT_rotate",
        "LIGHT_STUDIO_OT_reset_control_panel",
    }
    missing = [name for name in expected if not hasattr(bpy.types, name)]
    if missing:
        _fail(f"missing operator classes: {missing}")

    if control_panel.running_modals != 0:
        _fail(f"running_modals expected 0, got {control_panel.running_modals}")
    if control_panel.panel_global is not None:
        _fail("panel_global should be None at rest")

    # close_control_panel is a no-op when nothing is running.
    control_panel.close_control_panel()
    if control_panel.running_modals != 0:
        _fail("close_control_panel did not leave running_modals at 0")

    # multiprofile_conditions returns True when no modal is active.
    if not control_panel.multiprofile_conditions(bpy.context):
        _fail("multiprofile_conditions should return True at rest")

    # Keymap entries.
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc is None:
        _fail("no addon keyconfig")
    km = kc.keymaps.get("Object Mode")
    if km is None:
        _fail("no Object Mode keymap")
    bound = {(kmi.idname, kmi.type) for kmi in km.keymap_items}
    for op_id, key in (
        ("light_studio.grab", "G"),
        ("light_studio.scale", "S"),
        ("light_studio.rotate", "R"),
    ):
        if (op_id, key) not in bound:
            _fail(f"keymap entry missing: {op_id} on {key}")

    # App handlers registered.
    if control_panel._frame_change_handler not in bpy.app.handlers.frame_change_post:
        _fail("frame_change_handler not registered")
    if control_panel._load_handler not in bpy.app.handlers.load_post:
        _fail("load_handler not registered")

    addon_utils.disable(ADDON_ID, default_set=True)

    if control_panel._frame_change_handler in bpy.app.handlers.frame_change_post:
        _fail("frame_change_handler leaked after disable")
    if control_panel._load_handler in bpy.app.handlers.load_post:
        _fail("load_handler leaked after disable")
    if control_panel._addon_keymaps:
        _fail(f"keymap entries leaked after disable: {control_panel._addon_keymaps}")

    print("PASS: modal operators + keymaps + handlers register/unregister clean")


if __name__ == "__main__":
    main()
