"""Operators for LightStudio native Light Linking UI rows."""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty, IntProperty

from ..core import light_linking
from ..core.selected_light import selected_light_handle

_CATEGORY_ITEMS = (
    ("LIGHT", "Light Linking", "Light receiver linking"),
    ("SHADOW", "Shadow Linking", "Shadow blocker linking"),
)
_MODE_ITEMS = (
    ("INCLUDE", "In", "Include target"),
    ("EXCLUDE", "Ex", "Exclude target"),
)
_TARGET_TYPE_ITEMS = (
    ("OBJECT", "Object", "Object target"),
    ("COLLECTION", "Collection", "Collection target"),
)


def _active_handle(context: bpy.types.Context) -> bpy.types.Object | None:
    return selected_light_handle(context)


def _can_edit_light_linking(context: bpy.types.Context) -> bool:
    return (
        light_linking.has_native_light_linking_api()
        and light_linking.has_native_light_linking_row_state()
        and light_linking.is_valid_lightstudio_light(_active_handle(context))
    )


def _target_list_name(category: str, mode: str) -> str:
    if category == "LIGHT" and mode == "INCLUDE":
        return "light_linking_include_targets"
    if category == "LIGHT" and mode == "EXCLUDE":
        return "light_linking_exclude_targets"
    if category == "SHADOW" and mode == "INCLUDE":
        return "shadow_linking_include_targets"
    return "shadow_linking_exclude_targets"


class LLS_OT_AddLightLinkingTargetRow(bpy.types.Operator):
    bl_idname = "light_studio.add_light_linking_target_row"
    bl_label = "Add Light Linking Target"
    bl_description = "Add an empty Light Linking target row"

    category: EnumProperty(items=_CATEGORY_ITEMS)
    mode: EnumProperty(items=_MODE_ITEMS, default="INCLUDE")
    target_type: EnumProperty(items=_TARGET_TYPE_ITEMS, default="OBJECT")

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return _can_edit_light_linking(context)

    def execute(self, context: bpy.types.Context) -> set[str]:
        handle = _active_handle(context)
        if handle is None:
            return {"CANCELLED"}
        row = getattr(handle.LLStudio, _target_list_name(self.category, self.mode)).add()
        row.target_type = self.target_type
        light_linking.sync_light_linking_properties(handle)
        return {"FINISHED"}


class LLS_OT_SetLightLinkingTargetMode(bpy.types.Operator):
    bl_idname = "light_studio.set_light_linking_target_mode"
    bl_label = "Set Light Linking Target Mode"
    bl_description = "Switch a Light Linking target row between In and Ex"

    category: EnumProperty(items=_CATEGORY_ITEMS)
    from_mode: EnumProperty(items=_MODE_ITEMS)
    mode: EnumProperty(items=_MODE_ITEMS)
    index: IntProperty(default=-1)

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return _can_edit_light_linking(context)

    def execute(self, context: bpy.types.Context) -> set[str]:
        handle = _active_handle(context)
        if handle is None:
            return {"CANCELLED"}
        source_rows = getattr(handle.LLStudio, _target_list_name(self.category, self.from_mode))
        if not 0 <= self.index < len(source_rows):
            return {"CANCELLED"}

        source_row = source_rows[self.index]
        target_type = source_row.target_type
        object_target = source_row.object_target
        collection_target = source_row.collection_target
        source_rows.remove(self.index)

        destination = getattr(handle.LLStudio, _target_list_name(self.category, self.mode))
        row = destination.add()
        row.target_type = target_type
        if target_type == "COLLECTION":
            row.collection_target = collection_target
        else:
            row.object_target = object_target
        light_linking.sync_light_linking_properties(handle)
        return {"FINISHED"}


class LLS_OT_RemoveLightLinkingTargetRow(bpy.types.Operator):
    bl_idname = "light_studio.remove_light_linking_target_row"
    bl_label = "Remove Light Linking Target"
    bl_description = "Remove this Light Linking target row"

    category: EnumProperty(items=_CATEGORY_ITEMS)
    mode: EnumProperty(items=_MODE_ITEMS)
    index: IntProperty(default=-1)

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return _can_edit_light_linking(context)

    def execute(self, context: bpy.types.Context) -> set[str]:
        handle = _active_handle(context)
        if handle is None:
            return {"CANCELLED"}
        _remove_row(handle, self.category, self.mode, self.index)
        return {"FINISHED"}


class LLS_OT_ClearLightLinkingRow(bpy.types.Operator):
    bl_idname = "light_studio.clear_light_linking_row"
    bl_label = "Clear Light Linking Target"
    bl_description = "Clear this Light Linking target row"

    mode: EnumProperty(items=_MODE_ITEMS)
    index: IntProperty(default=-1)

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return _can_edit_light_linking(context)

    def execute(self, context: bpy.types.Context) -> set[str]:
        handle = _active_handle(context)
        if handle is None:
            return {"CANCELLED"}
        _remove_row(handle, "LIGHT", self.mode, self.index)
        return {"FINISHED"}


class LLS_OT_ClearShadowLinkingRow(bpy.types.Operator):
    bl_idname = "light_studio.clear_shadow_linking_row"
    bl_label = "Clear Shadow Linking Target"
    bl_description = "Clear this Shadow Linking target row"

    mode: EnumProperty(items=_MODE_ITEMS)
    index: IntProperty(default=-1)

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return _can_edit_light_linking(context)

    def execute(self, context: bpy.types.Context) -> set[str]:
        handle = _active_handle(context)
        if handle is None:
            return {"CANCELLED"}
        _remove_row(handle, "SHADOW", self.mode, self.index)
        return {"FINISHED"}


def _remove_row(
    handle: bpy.types.Object,
    category: str,
    mode: str,
    index: int,
) -> None:
    light_linking.remove_light_linking_target_row(handle, category, mode, index)


classes: tuple[type[bpy.types.Operator], ...] = (
    LLS_OT_AddLightLinkingTargetRow,
    LLS_OT_SetLightLinkingTargetMode,
    LLS_OT_RemoveLightLinkingTargetRow,
    LLS_OT_ClearLightLinkingRow,
    LLS_OT_ClearShadowLinkingRow,
)
