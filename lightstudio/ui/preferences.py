"""Add-on preferences for LeoMoon LightStudio.

Step 16 fills ``draw()`` with the ``rna_keymap_ui`` editor for every
keymap entry registered by :mod:`lightstudio.handlers.keymaps`
(F brush, Ctrl+F brush-add, Shift+D duplicate-move, Del custom-delete,
G/S/R modal sub-operators).
"""

from __future__ import annotations

import bpy
import rna_keymap_ui


_PANEL_BG_DEFAULT = (0.05, 0.05, 0.05)
_PANEL_GRID_DEFAULT = (0.12, 0.12, 0.12)


class LLSPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__.rsplit(".", 1)[0]

    panel_bg_color: bpy.props.FloatVectorProperty(  # type: ignore[valid-type]
        name="Control Panel Background",
        description="Background color of the light control panel overlay",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=_PANEL_BG_DEFAULT,
    )
    panel_grid_color: bpy.props.FloatVectorProperty(  # type: ignore[valid-type]
        name="Control Panel Grid",
        description="Color of the faint grid lines drawn on the control panel",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=_PANEL_GRID_DEFAULT,
    )

    def draw(self, context: bpy.types.Context) -> None:
        from ..handlers.keymaps import iter_keymap_items

        layout = self.layout
        box = layout.box()
        box.label(text="Keymap", icon="KEYINGSET")
        col = box.column()
        wm = context.window_manager
        kc = wm.keyconfigs.user
        for km, kmi in iter_keymap_items():
            user_km = kc.keymaps.get(km.name)
            if user_km is None:
                continue
            rna_keymap_ui.draw_kmi(
                ["ADDON", "USER", "DEFAULT"], kc, user_km, kmi, col, 0
            )

        misc = layout.box()
        misc.label(text="Misc", icon="PREFERENCES")
        misc.label(text="Control Panel Colors:")
        split = misc.split(factor=0.5, align=True)
        col = split.column(align=True)
        col.prop(self, "panel_bg_color", text="Background")
        col = split.column(align=True)
        col.prop(self, "panel_grid_color", text="Grid")


def get_prefs():
    """Return the addon preferences instance, or ``None`` if unavailable."""
    try:
        addon = bpy.context.preferences.addons.get(LLSPreferences.bl_idname)
    except (AttributeError, RuntimeError):
        return None
    return addon.preferences if addon else None


def get_panel_bg_color() -> tuple[float, float, float, float]:
    prefs = get_prefs()
    if prefs is None:
        return (*_PANEL_BG_DEFAULT, 1.0)
    c = prefs.panel_bg_color
    return (c[0], c[1], c[2], 1.0)


def get_panel_grid_color() -> tuple[float, float, float, float]:
    prefs = get_prefs()
    if prefs is None:
        return (*_PANEL_GRID_DEFAULT, 1.0)
    c = prefs.panel_grid_color
    return (c[0], c[1], c[2], 1.0)


classes: tuple[type[bpy.types.AddonPreferences], ...] = (LLSPreferences,)
