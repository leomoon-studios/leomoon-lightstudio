"""Selected Light panel — type switch + per-type controls + distance."""

from __future__ import annotations

import os

import bpy

from ...core import light_linking
from ...core.material_inspect import get_advanced_inputs
from ...core.scene_utils import family, find_light_grp
from .._common import PANEL_CATEGORY, PANEL_REGION, PANEL_SPACE, studio_initialized

_INT_SOCKET_PROPS = {
    "Mask - Grid Columns": "mask_grid_columns",
    "Mask - Grid Rows": "mask_grid_rows",
}


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


def _target_list_name(category: str, mode: str) -> str:
    if category == "LIGHT" and mode == "INCLUDE":
        return "light_linking_include_targets"
    if category == "LIGHT" and mode == "EXCLUDE":
        return "light_linking_exclude_targets"
    if category == "SHADOW" and mode == "INCLUDE":
        return "shadow_linking_include_targets"
    return "shadow_linking_exclude_targets"


def _draw_light_linking_section(
    layout: bpy.types.UILayout,
    handle: bpy.types.Object,
) -> None:
    if not (
        light_linking.has_native_light_linking_api()
        and light_linking.has_native_light_linking_row_state()
    ):
        return

    layout.separator()
    col = layout.column(align=True)
    _draw_target_group(
        col,
        handle,
        "Light Linking",
        "LIGHT",
        "show_light_linking",
    )
    col.separator()
    _draw_target_group(
        col,
        handle,
        "Shadow Linking",
        "SHADOW",
        "show_shadow_linking",
    )


def _draw_target_group(
    layout: bpy.types.UILayout,
    handle: bpy.types.Object,
    label: str,
    category: str,
    expanded_prop: str,
) -> None:
    box = layout.box()
    header = box.row(align=True)
    is_expanded = bool(getattr(handle.LLStudio, expanded_prop))
    header.prop(
        handle.LLStudio,
        expanded_prop,
        text=label,
        icon="TRIA_DOWN" if is_expanded else "TRIA_RIGHT",
        emboss=False,
    )
    if not is_expanded:
        return

    add_object = header.operator(
        "light_studio.add_light_linking_target_row",
        text="",
        icon="OBJECT_DATA",
    )
    add_object.category = category
    add_object.mode = "INCLUDE"
    add_object.target_type = "OBJECT"
    add_collection = header.operator(
        "light_studio.add_light_linking_target_row",
        text="",
        icon="OUTLINER_COLLECTION",
    )
    add_collection.category = category
    add_collection.mode = "INCLUDE"
    add_collection.target_type = "COLLECTION"

    body = box.column(align=True)
    rows_drawn = 0
    for mode in ("INCLUDE", "EXCLUDE"):
        rows = getattr(handle.LLStudio, _target_list_name(category, mode))
        for index, item in enumerate(rows):
            _draw_target_row(body, item, category, mode, index)
            rows_drawn += 1
    if rows_drawn == 0:
        body.label(text="None")


def _draw_target_row(
    layout: bpy.types.UILayout,
    item: bpy.types.PropertyGroup,
    category: str,
    mode: str,
    index: int,
) -> None:
    row = layout.row(align=True)
    target_row = row.row(align=True)
    if item.target_type == "COLLECTION":
        target_row.prop(item, "collection_target", text="")
    else:
        target_row.prop(item, "object_target", text="")

    controls = row.row(align=True)
    controls.ui_units_x = 6.5
    in_op = controls.operator(
        "light_studio.set_light_linking_target_mode",
        text="In",
        depress=mode == "INCLUDE",
    )
    in_op.category = category
    in_op.from_mode = mode
    in_op.mode = "INCLUDE"
    in_op.index = index

    ex_op = controls.operator(
        "light_studio.set_light_linking_target_mode",
        text="Ex",
        depress=mode == "EXCLUDE",
    )
    ex_op.category = category
    ex_op.from_mode = mode
    ex_op.mode = "EXCLUDE"
    ex_op.index = index

    clear_operator = (
        "light_studio.clear_light_linking_row"
        if category == "LIGHT"
        else "light_studio.clear_shadow_linking_row"
    )
    remove_op = controls.operator(
        clear_operator,
        text="",
        icon="X",
    )
    remove_op.mode = mode
    remove_op.index = index


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
                        elif socket.name in _INT_SOCKET_PROPS:
                            sub_col.prop(
                                light_mesh.LLStudio,
                                _INT_SOCKET_PROPS[socket.name],
                                slider=True,
                                text=socket.name,
                            )
                        else:
                            sub_col.prop(
                                socket, "default_value", text=socket.name
                            )

        light_mesh = _active_light_mesh(context)
        if light_mesh is not None and light_mesh.parent is not None:
            col.prop(light_mesh.parent, "location", index=2, text="Distance")

        handle = light_linking.resolve_light_handle(obj)
        if handle is not None and light_linking.is_valid_lightstudio_light(obj):
            _draw_light_linking_section(layout, handle)


classes: tuple[type[bpy.types.Panel], ...] = (LLS_PT_Selected,)
