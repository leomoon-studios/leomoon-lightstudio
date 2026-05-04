"""Profiles panel — UIList + CRUD + handle constraint controls."""

from __future__ import annotations

import bpy

from .._common import PANEL_CATEGORY, PANEL_REGION, PANEL_SPACE, studio_initialized


class LLS_PT_ProfileList(bpy.types.Panel):
    bl_idname = "LLS_PT_profile_list"
    bl_label = "Profiles"
    bl_space_type = PANEL_SPACE
    bl_region_type = PANEL_REGION
    bl_category = PANEL_CATEGORY

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return studio_initialized(context)

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        props = context.scene.LLStudio

        row = layout.row()
        col = row.column()
        col.prop(props, "profile_multimode", expand=True)
        col.template_list(
            "LLS_UL_ProfileList",
            "Profile_List",
            props,
            "profile_list",
            props,
            "profile_list_index",
            rows=5,
        )

        col = row.column(align=True)
        col.operator("lls_list.new_profile", icon="ADD", text="")
        col.operator("lls_list.delete_profile", icon="REMOVE", text="")
        col.operator("lls_list.copy_profile_menu", icon="DUPLICATE", text="")
        col.separator()
        col.operator("lls_list.move_profile", text="", icon="TRIA_UP").direction = "UP"
        col.operator(
            "lls_list.move_profile", text="", icon="TRIA_DOWN"
        ).direction = "DOWN"

        col = layout.column(align=True)
        col.operator("lls_list.select_profile_handle")

        if not props.profile_list:
            return
        index = props.profile_list_index
        if index >= len(props.profile_list):
            return
        empty_name = props.profile_list[index].empty_name
        if empty_name not in bpy.data.objects:
            return
        handles = [
            o
            for o in bpy.data.objects[empty_name].children
            if o.name.startswith("LLS_HANDLE")
        ]
        if not handles:
            return
        handle = handles[0]
        row = col.row(align=True)
        if "LLS Child Of" in handle.constraints:
            row.prop(
                handle.constraints["LLS Child Of"],
                "target",
                expand=True,
                text="Constrain to",
            )
            row.operator(
                "lls_list.constraint_toggle_parent_inverse",
                text="",
                icon="ORIENTATION_PARENT",
            )
            row.operator("lls_list.remove_constraint", text="", icon="X")
        else:
            row.operator("lls_list.create_profile_constraint")


classes: tuple[type[bpy.types.Panel], ...] = (LLS_PT_ProfileList,)
