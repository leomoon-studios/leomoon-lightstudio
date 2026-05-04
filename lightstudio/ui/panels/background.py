"""Background panel — set background + transparent toggle."""

from __future__ import annotations

import bpy

from .._common import PANEL_CATEGORY, PANEL_REGION, PANEL_SPACE, studio_initialized


class LLS_PT_Background(bpy.types.Panel):
    bl_idname = "LLS_PT_background"
    bl_label = "Background"
    bl_space_type = PANEL_SPACE
    bl_region_type = PANEL_REGION
    bl_category = PANEL_CATEGORY

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return studio_initialized(context)

    def draw(self, context: bpy.types.Context) -> None:
        col = self.layout.column(align=True)
        col.operator("scene.set_light_studio_background")
        col.prop(
            context.scene.render, "film_transparent", text="Transparent Background"
        )


classes: tuple[type[bpy.types.Panel], ...] = (LLS_PT_Background,)
