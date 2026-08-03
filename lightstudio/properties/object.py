"""Object-level PropertyGroups for LeoMoon LightStudio.

Ported from legacy ``light_operators.py`` (LeoMoon_Light_Studio_Object_Properties)
and ``light_list.py`` (LightListItem).

Update / get / set callbacks that depend on operators or helpers that
have not been ported yet (light_list view-layer lookups, salvage_data
fallback in ``active_light_type_update``) are stubbed with TODO markers
and will be restored alongside their consumers in steps 10-12.
"""

from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

_GRID_INPUT_NAMES = {
    "mask_grid_columns": "Mask - Grid Columns",
    "mask_grid_rows": "Mask - Grid Rows",
}


def _light_list_item_name_update(self: LightListItem, context: bpy.types.Context) -> None:
    obj = bpy.data.objects.get(self.handle_name)
    if obj is not None:
        obj.LLStudio.light_name = self.name


def _light_list_item_mute_get(self: LightListItem) -> bool:
    from ..operators.light import light_item_mute_get
    return light_item_mute_get(self.handle_name)


def _light_list_item_mute_set(self: LightListItem, value: bool) -> None:
    from ..operators.light import light_item_mute_set
    light_item_mute_set(self.handle_name, value)


def _light_list_item_visible_camera_get(self: LightListItem) -> bool:
    from ..operators.light import light_item_visible_camera_get
    return light_item_visible_camera_get(self.handle_name)


def _light_list_item_visible_camera_set(self: LightListItem, value: bool) -> None:
    from ..operators.light import light_item_visible_camera_set
    light_item_visible_camera_set(self.handle_name, value)


class LightListItem(PropertyGroup):
    """One entry in ``Scene.LLStudio.light_list`` (drives the UIList)."""

    name: StringProperty(name="Light Name", default="Untitled", update=_light_list_item_name_update)
    handle_name: StringProperty(default="")
    mute: BoolProperty(get=_light_list_item_mute_get, set=_light_list_item_mute_set)
    visible_camera: BoolProperty(
        get=_light_list_item_visible_camera_get,
        set=_light_list_item_visible_camera_set,
    )
    exclude_isolate: IntProperty(default=-1)


def _light_linking_target_update(
    self: LightLinkingTargetItem,
    context: bpy.types.Context,
) -> None:
    handle = self.id_data
    if not isinstance(handle, bpy.types.Object):
        return
    from ..core.light_linking import sync_light_linking_properties

    sync_light_linking_properties(handle)


class LightLinkingTargetItem(PropertyGroup):
    """One object or collection assigned to a LightStudio light-linking bucket."""

    target_type: EnumProperty(
        name="Target Type",
        items=(
            ("OBJECT", "Object", "Blender object target"),
            ("COLLECTION", "Collection", "Blender collection target"),
        ),
        default="OBJECT",
        update=_light_linking_target_update,
    )
    object_target: PointerProperty(
        name="Object",
        type=bpy.types.Object,
        update=_light_linking_target_update,
    )
    collection_target: PointerProperty(
        name="Collection",
        type=bpy.types.Collection,
        update=_light_linking_target_update,
    )


def _active_light_type_update(self: LeoMoon_Light_Studio_Object_Properties, context: bpy.types.Context) -> None:
    """Toggle Basic (area light) vs Advanced (mesh light) visibility.

    Mirrors legacy ``active_light_type_update``: each LLS light contains
    two sibling collections (``LLS_Basic`` + ``LLS_Advanced``); only one
    is enabled at a time via the layer-collection ``exclude`` flag.
    """
    light_handle = self.id_data
    if not isinstance(light_handle, bpy.types.Object):
        return

    from ..core.scene_utils import sync_light_type_visibility

    sync_light_type_visibility(light_handle, context, select_active=True)

    from ..core.light_linking import sync_light_linking_properties

    sync_light_linking_properties(light_handle)


def _grid_input_get(self: LeoMoon_Light_Studio_Object_Properties, prop_name: str) -> int:
    obj = self.id_data
    socket_name = _GRID_INPUT_NAMES[prop_name]
    try:
        socket = obj.active_material.node_tree.nodes["Group"].inputs[socket_name]
        return int(round(socket.default_value))
    except (AttributeError, KeyError, TypeError):
        return 0


def _grid_input_set(
    self: LeoMoon_Light_Studio_Object_Properties, prop_name: str, value: int
) -> None:
    obj = self.id_data
    socket_name = _GRID_INPUT_NAMES[prop_name]
    try:
        socket = obj.active_material.node_tree.nodes["Group"].inputs[socket_name]
        socket.default_value = int(value)
    except (AttributeError, KeyError, TypeError):
        return


def _mask_grid_columns_get(self: LeoMoon_Light_Studio_Object_Properties) -> int:
    return _grid_input_get(self, "mask_grid_columns")


def _mask_grid_columns_set(
    self: LeoMoon_Light_Studio_Object_Properties, value: int
) -> None:
    _grid_input_set(self, "mask_grid_columns", value)


def _mask_grid_rows_get(self: LeoMoon_Light_Studio_Object_Properties) -> int:
    return _grid_input_get(self, "mask_grid_rows")


def _mask_grid_rows_set(self: LeoMoon_Light_Studio_Object_Properties, value: int) -> None:
    _grid_input_set(self, "mask_grid_rows", value)


class LeoMoon_Light_Studio_Object_Properties(PropertyGroup):
    """Per-object LLS metadata attached to ``Object.LLStudio``."""

    light_name: StringProperty()
    order_index: IntProperty()
    mute: BoolProperty()
    type: EnumProperty(
        name="Light Type",
        items=(
            ("ADVANCED", "Advanced", "Cycles only"),
            ("BASIC", "Basic", "Cycles & EEVEE"),
        ),
        default="ADVANCED",
        update=_active_light_type_update,
    )
    mask_grid_columns: IntProperty(
        name="Mask - Grid Columns",
        min=0,
        soft_max=100,
        get=_mask_grid_columns_get,
        set=_mask_grid_columns_set,
    )
    mask_grid_rows: IntProperty(
        name="Mask - Grid Rows",
        min=0,
        soft_max=100,
        get=_mask_grid_rows_get,
        set=_mask_grid_rows_set,
    )
    show_light_linking: BoolProperty(name="Light Linking", default=True)
    show_shadow_linking: BoolProperty(name="Shadow Linking", default=True)
    light_linking_include_targets: CollectionProperty(type=LightLinkingTargetItem)
    light_linking_exclude_targets: CollectionProperty(type=LightLinkingTargetItem)
    shadow_linking_include_targets: CollectionProperty(type=LightLinkingTargetItem)
    shadow_linking_exclude_targets: CollectionProperty(type=LightLinkingTargetItem)


classes: tuple[type[PropertyGroup], ...] = (
    LightListItem,
    LightLinkingTargetItem,
    LeoMoon_Light_Studio_Object_Properties,
)
