"""Lights panel — per-profile UIList + CRUD + reorder."""

from __future__ import annotations

import bpy

from .._common import PANEL_CATEGORY, PANEL_REGION, PANEL_SPACE, has_profile


class LLS_PT_Lights(bpy.types.Panel):
    bl_idname = "LLS_PT_lights"
    bl_label = "Lights"
    bl_space_type = PANEL_SPACE
    bl_region_type = PANEL_REGION
    bl_category = PANEL_CATEGORY

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return has_profile(context)

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        props = context.scene.LLStudio

        row = layout.row()
        col = row.column()
        if (
            props.profile_multimode
            and props.profile_list_index < len(props.profile_list)
        ):
            col.label(
                text="Profile: " + props.profile_list[props.profile_list_index].name
            )
        col.template_list(
            "LLS_UL_LightList",
            "Light_List",
            props,
            "light_list",
            props,
            "light_list_index",
            rows=5,
        )

        col = row.column(align=True)
        col.operator("scene.add_leomoon_studio_light", icon="ADD", text="")
        col.operator(
            "scene.delete_leomoon_studio_light", icon="REMOVE", text=""
        ).confirm = False
        col.operator("lls_list.copy_light", icon="DUPLICATE", text="")
        col.separator()
        col.operator("lls_list.move_light", text="", icon="TRIA_UP").direction = "UP"
        col.operator(
            "lls_list.move_light", text="", icon="TRIA_DOWN"
        ).direction = "DOWN"


classes: tuple[type[bpy.types.Panel], ...] = (LLS_PT_Lights,)
