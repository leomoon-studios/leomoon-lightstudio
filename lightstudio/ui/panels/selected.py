"""Selected Light panel — type switch + per-type controls + distance."""

from __future__ import annotations

import os

import bpy

from ...core.material_inspect import get_advanced_inputs
from ...core.scene_utils import family, find_light_grp
from .._common import PANEL_CATEGORY, PANEL_REGION, PANEL_SPACE, studio_initialized


def _active_light_mesh(context: bpy.types.Context) -> bpy.types.Object | None:
    obj = context.active_object
    if obj is None:
        return None
    lg = find_light_grp(obj)
    if lg is None:
        return None
    for child in family(lg):
        if child.name.startswith("LLS_LIGHT_MESH"):
            return child
    return None


class LLS_PT_Selected(bpy.types.Panel):
    bl_idname = "LLS_PT_selected"
    bl_label = "Selected Light"
    bl_space_type = PANEL_SPACE
    bl_region_type = PANEL_REGION
    bl_category = PANEL_CATEGORY

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return studio_initialized(context)

    def draw(self, context: bpy.types.Context) -> None:
        obj = context.active_object
        if not (obj and obj.name.startswith("LLS_LIGHT_") and obj.parent):
            return
        layout = self.layout
        wm = context.window_manager

        col = layout.column(align=True)
        row = col.row()
        row.prop(obj.parent.LLStudio, "type", expand=True)
        if context.scene.render.engine == "BLENDER_EEVEE":
            row.enabled = False
        col.separator()

        if obj.type == "LIGHT":
            row = col.row()
            row.prop(obj.data.LLStudio, "color")
            col.prop(obj.data.LLStudio, "color_saturation", slider=True)
            col.prop(obj.data.LLStudio, "intensity")
        elif obj.type == "MESH":
            box = layout.box()
            inner = box.column()
            inner.template_icon_view(wm, "lls_tex_previews", show_labels=True)
            inner.label(text=os.path.splitext(wm.lls_tex_previews)[0])

            layout.separator()
            light_mesh = _active_light_mesh(context)
            if (
                light_mesh is None
                or not light_mesh.active_material
                or not light_mesh.active_material.node_tree
            ):
                inner.label(text="LLS_light material is not valid.")
            else:
                inputs = get_advanced_inputs(light_mesh.active_material)
                if not inputs:
                    inner.label(text="LLS_light material is not valid.")
                else:
                    sub_col = layout.column(align=True)
                    nodes = light_mesh.active_material.node_tree.nodes
                    group_inputs = nodes["Group"].inputs
                    for socket in group_inputs[2:]:
                        if socket.type == "RGBA":
                            layout.prop(socket, "default_value", text=socket.name)
                            sub_col = layout.column(align=True)
                        else:
                            sub_col.prop(
                                socket, "default_value", text=socket.name
                            )

        light_mesh = _active_light_mesh(context)
        if light_mesh is not None and light_mesh.parent is not None:
            col.prop(light_mesh.parent, "location", index=2, text="Distance")


classes: tuple[type[bpy.types.Panel], ...] = (LLS_PT_Selected,)
