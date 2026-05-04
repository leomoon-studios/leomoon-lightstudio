"""Central keymap registration (Step 16).

The legacy add-on scattered keymap registration across
``light_brush.py``, ``deleteOperator.py``, and ``operators/modal.py``
with a timer-based fallback for the ``object.delete`` interception.
Extension load order is well-defined, so a single ``register()`` call
invoked from ``handlers.register()`` suffices.

Every entry registered here is editable through ``LLSPreferences``
via :func:`iter_keymap_items`.
"""

from __future__ import annotations

import contextlib

import bpy

from ..operators import light_brush
from ..operators.delete import LLS_OT_DeleteCustom
from ..operators.modal import control_panel

_addon_keymaps: list[tuple[bpy.types.KeyMap, bpy.types.KeyMapItem]] = []


# (Operator class, key, value, modifier-kwargs, properties)
_ENTRIES: tuple = (
    (light_brush.OT_LLSFast3DEdit, "F", "PRESS", {}, {"continuous": False}),
    (light_brush.OT_LLS3DAddLight, "F", "PRESS", {"ctrl": True}, {"continuous": False}),
    # Shift+D wrapper for LLS_OT_DuplicateMove (light copy via Shift+D).
    ("lls_object.duplicate_move", "D", "PRESS", {"shift": True}, {}),
)


def _register_delete_kmis(km: bpy.types.KeyMap) -> None:
    """Register a custom-delete kmi mirroring every default ``object.delete`` kmi."""
    user_km = bpy.context.window_manager.keyconfigs.user.keymaps.get("Object Mode")
    default_kmis = []
    if user_km is not None:
        default_kmis = [
            kmi for kmi in user_km.keymap_items if kmi.idname == "object.delete"
        ]

    if not default_kmis:
        # Fall back to a single Del binding if no default exists.
        kmi = km.keymap_items.new(
            LLS_OT_DeleteCustom.bl_idname, "DEL", "PRESS"
        )
        _addon_keymaps.append((km, kmi))
        return

    for default_kmi in default_kmis:
        kmi = km.keymap_items.new(
            LLS_OT_DeleteCustom.bl_idname, default_kmi.type, default_kmi.value
        )
        kmi.map_type = default_kmi.map_type
        if hasattr(kmi, "repeat"):
            kmi.repeat = default_kmi.repeat
        kmi.any = default_kmi.any
        kmi.shift = default_kmi.shift
        kmi.ctrl = default_kmi.ctrl
        kmi.alt = default_kmi.alt
        kmi.oskey = default_kmi.oskey
        kmi.key_modifier = default_kmi.key_modifier
        if hasattr(default_kmi.properties, "use_global"):
            kmi.properties.use_global = default_kmi.properties.use_global
        if hasattr(default_kmi.properties, "confirm"):
            kmi.properties.confirm = default_kmi.properties.confirm
        _addon_keymaps.append((km, kmi))


def register() -> None:
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc is None:
        return
    km = kc.keymaps.new(name="Object Mode", space_type="EMPTY")

    for op, key, value, mods, props in _ENTRIES:
        idname = op if isinstance(op, str) else op.bl_idname
        kmi = km.keymap_items.new(idname, key, value, **mods)
        for prop_name, prop_value in props.items():
            with contextlib.suppress(AttributeError, TypeError):
                setattr(kmi.properties, prop_name, prop_value)
        _addon_keymaps.append((km, kmi))

    _register_delete_kmis(km)

    # G/S/R for the modal control panel (delegated to the modal module
    # since it owns the operator references).
    control_panel.add_shortkeys()


def unregister() -> None:
    control_panel.remove_shortkeys()
    for km, kmi in _addon_keymaps:
        with contextlib.suppress(RuntimeError, ReferenceError):
            km.keymap_items.remove(kmi)
    _addon_keymaps.clear()


def iter_keymap_items():
    """Yield ``(km, kmi)`` for every entry registered by this module.

    Used by :class:`LLSPreferences.draw` to render an editable keymap UI.
    Includes the modal G/S/R entries owned by ``control_panel``.
    """
    yield from _addon_keymaps
    yield from control_panel._addon_keymaps
