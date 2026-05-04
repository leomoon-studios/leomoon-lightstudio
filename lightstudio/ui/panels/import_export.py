"""Import / Export panel — EXR bake + profile import/export."""

from __future__ import annotations

import bpy

from .._common import PANEL_CATEGORY, PANEL_REGION, PANEL_SPACE, op_registered, studio_initialized


class LLS_PT_ProfileImportExport(bpy.types.Panel):
    bl_idname = "LLS_PT_profile_import_export"
    bl_label = "Import/Export"
    bl_space_type = PANEL_SPACE
    bl_region_type = PANEL_REGION
    bl_category = PANEL_CATEGORY

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return studio_initialized(context)

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout

        box = layout.box()
        box.label(text="Animation not supported.", icon="ERROR")

        col = layout.column(align=True)
        if op_registered("LLS_OT_render_lights_exr"):
            col.operator("lls.render_lights_exr")
        else:
            col.label(text="EXR render: pending (step 17)", icon="INFO")
        col.operator("lls_list.export_profiles", text="Export Selected Profile")
        col.operator(
            "lls_list.export_profiles", text="Export All Profiles"
        ).all = True
        col.operator("lls_list.import_profiles", text="Import Profiles")


classes: tuple[type[bpy.types.Panel], ...] = (LLS_PT_ProfileImportExport,)
