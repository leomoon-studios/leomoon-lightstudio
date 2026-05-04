"""Mode panel — selects the current ``lls_mode`` (NORMAL / ANIMATION)."""

from __future__ import annotations

import bpy

from .._common import PANEL_CATEGORY, PANEL_REGION, PANEL_SPACE, op_registered, studio_initialized


class LLS_PT_Mode(bpy.types.Panel):
    bl_idname = "LLS_PT_mode"
    bl_label = "Mode"
    bl_space_type = PANEL_SPACE
    bl_region_type = PANEL_REGION
    bl_category = PANEL_CATEGORY

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return studio_initialized(context)

    def draw(self, context: bpy.types.Context) -> None:
        props = context.scene.LLStudio
        layout = self.layout
        row = layout.row(align=True)
        row.prop(props, "lls_mode", expand=True)

        if props.lls_mode == "ANIMATION" and op_registered(
            "LLS_OT_insert_key_active_light"
        ):
            sub = layout.column(align=True)
            sub.enabled = bpy.ops.lls.insert_key_active_light.poll()
            sub.operator(
                "lls.insert_key_active_light",
                text="Insert Key for Active Light",
                icon="KEY_HLT",
            )


classes: tuple[type[bpy.types.Panel], ...] = (LLS_PT_Mode,)
