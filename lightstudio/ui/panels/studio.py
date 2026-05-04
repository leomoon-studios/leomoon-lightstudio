"""Studio panel — create/delete + control panel + render engine switcher."""

from __future__ import annotations

import bpy

from .._common import PANEL_CATEGORY, PANEL_REGION, PANEL_SPACE, in_object_mode


class LLS_PT_Studio(bpy.types.Panel):
    bl_idname = "LLS_PT_studio"
    bl_label = "Studio"
    bl_space_type = PANEL_SPACE
    bl_region_type = PANEL_REGION
    bl_category = PANEL_CATEGORY

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return in_object_mode(context)

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        col = layout.column(align=True)
        if not context.scene.LLStudio.initialized:
            col.operator("scene.create_leomoon_light_studio")
        else:
            col.operator("scene.delete_leomoon_light_studio")
        col.separator()

        col.operator("light_studio.control_panel", icon="MENU_PANEL")

        sub = col.row(align=True)
        sub.operator(
            "scene.switch_to_renderer",
            text="Cycles",
            depress=context.scene.render.engine == "CYCLES",
        ).engine = "CYCLES"
        sub.operator(
            "scene.switch_to_renderer",
            text="EEVEE",
            depress=context.scene.render.engine == "BLENDER_EEVEE",
        ).engine = "BLENDER_EEVEE"


classes: tuple[type[bpy.types.Panel], ...] = (LLS_PT_Studio,)
