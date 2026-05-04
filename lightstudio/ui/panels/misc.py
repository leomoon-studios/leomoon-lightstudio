"""Misc panel — camera visibility toggles, texture utils, keying set."""

from __future__ import annotations

import bpy

from .._common import PANEL_CATEGORY, PANEL_REGION, PANEL_SPACE, op_registered, studio_initialized


class LLS_PT_Misc(bpy.types.Panel):
    bl_idname = "LLS_PT_misc"
    bl_label = "Misc"
    bl_space_type = PANEL_SPACE
    bl_region_type = PANEL_REGION
    bl_category = PANEL_CATEGORY

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return studio_initialized(context)

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        col = layout.column(align=True)
        col.operator(
            "lls.camera_toggle_all_lights", text="Show Lights in Camera"
        ).visible_camera = True
        col.operator(
            "lls.camera_toggle_all_lights", text="Hide Lights in Camera"
        ).visible_camera = False
        col.operator("lls.find_missing_textures")
        col.operator("lls.open_textures_folder")
        col.operator("light_studio.reset_control_panel")
        if op_registered("LLS_OT_lls_keyingset"):
            col.operator("lls.lls_keyingset")
            active = context.scene.keying_sets.active
            if active and active.bl_idname == "BUILTIN_KSI_LightStudio":
                box = layout.box()
                box.label(text="Keying Set is active.", icon="CHECKMARK")


classes: tuple[type[bpy.types.Panel], ...] = (LLS_PT_Misc,)
