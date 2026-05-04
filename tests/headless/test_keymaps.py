"""Headless verification: Step 16 central keymap registration.

Asserts:

1. ``handlers.keymaps.register()`` binds:
   - ``light_studio.fast_3d_edit`` on F (no modifiers)
   - ``light_studio.add_light_3d`` on F (Ctrl)
   - ``lls_object.duplicate_move`` on D (Shift)
   - At least one ``object.delete_custom`` entry
2. The G/S/R modal entries (delegated to ``control_panel.add_shortkeys``)
   are also registered exactly once (no double-registration).
3. ``LLSPreferences`` is registered as the addon preferences class.
4. After ``addon_utils.disable``, both ``handlers.keymaps._addon_keymaps``
   and ``control_panel._addon_keymaps`` are empty (no leftover bindings).

Run with::

    blender --background --factory-startup \\
        --python tests/headless/test_keymaps.py
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

    from bl_ext.user_default.leomoon_lightstudio.handlers import keymaps
    from bl_ext.user_default.leomoon_lightstudio.operators.modal import control_panel

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc is None:
        _fail("no addon keyconfig")
    km = kc.keymaps.get("Object Mode")
    if km is None:
        _fail("no Object Mode keymap")

    # Build a (idname, type, ctrl, shift, alt) summary for assertions.
    bound = [
        (kmi.idname, kmi.type, kmi.ctrl, kmi.shift, kmi.alt)
        for kmi in km.keymap_items
    ]

    expected_modifiers = [
        ("light_studio.fast_3d_edit", "F", False, False, False),
        ("light_studio.add_light_3d", "F", True, False, False),
        ("lls_object.duplicate_move", "D", False, True, False),
    ]
    for entry in expected_modifiers:
        if entry not in bound:
            _fail(f"missing keymap entry: {entry}")

    delete_custom = [b for b in bound if b[0] == "object.delete_custom"]
    if not delete_custom:
        _fail("no object.delete_custom keymap entry registered")

    # G/S/R are also bound (delegated, no double-registration).
    for op_id, key in (
        ("light_studio.grab", "G"),
        ("light_studio.scale", "S"),
        ("light_studio.rotate", "R"),
    ):
        matches = [b for b in bound if b[0] == op_id and b[1] == key]
        if len(matches) != 1:
            _fail(f"{op_id} on {key}: expected 1 binding, got {len(matches)}")

    # iter_keymap_items() exposes every entry for the preferences UI.
    iter_count = sum(1 for _ in keymaps.iter_keymap_items())
    expected_min = len(expected_modifiers) + len(delete_custom) + 3  # G/S/R
    if iter_count < expected_min:
        _fail(
            f"iter_keymap_items returned {iter_count}, expected >= {expected_min}"
        )

    # LLSPreferences registered.
    prefs = bpy.context.preferences.addons.get(ADDON_ID)
    if prefs is None or prefs.preferences is None:
        _fail("LLSPreferences not attached to addon")

    addon_utils.disable(ADDON_ID, default_set=True)

    if keymaps._addon_keymaps:
        _fail(f"keymaps._addon_keymaps leaked: {keymaps._addon_keymaps}")
    if control_panel._addon_keymaps:
        _fail(
            f"control_panel._addon_keymaps leaked: {control_panel._addon_keymaps}"
        )

    print("PASS: central keymap registry binds F/Ctrl+F/Shift+D/Del + G/S/R clean")


if __name__ == "__main__":
    main()
