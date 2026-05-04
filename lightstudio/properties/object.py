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
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup


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


def _active_light_type_update(self: LeoMoon_Light_Studio_Object_Properties, context: bpy.types.Context) -> None:
    """Toggle Basic (area light) vs Advanced (mesh light) visibility.

    Mirrors legacy ``active_light_type_update``: each LLS light contains
    two sibling collections (``LLS_Basic`` + ``LLS_Advanced``); only one
    is enabled at a time via the layer-collection ``exclude`` flag.
    """
    from ..core.scene_utils import find_view_layer

    scene_props = context.scene.LLStudio
    try:
        list_item = scene_props.light_list[self.order_index]
        light_handle = bpy.data.objects[list_item.handle_name]
    except (IndexError, KeyError):
        return

    basic_cols = [
        child.users_collection[0]
        for child in light_handle.children
        if child.type == "LIGHT" and child.users_collection
    ]
    advanced_cols = [
        child.users_collection[0]
        for child in light_handle.children
        if child.type == "MESH" and child.users_collection
    ]
    if not basic_cols or not advanced_cols:
        return
    basic_col = basic_cols[0]
    advanced_col = advanced_cols[0]

    basic_view = find_view_layer(basic_col, context.view_layer.layer_collection)
    advanced_view = find_view_layer(
        advanced_col, context.view_layer.layer_collection
    )
    if basic_view is None or advanced_view is None:
        return

    if self.type == "ADVANCED":
        basic_view.exclude = True
        advanced_view.exclude = False
        target = advanced_col.objects[0] if advanced_col.objects else None
    else:
        basic_view.exclude = False
        advanced_view.exclude = True
        target = basic_col.objects[0] if basic_col.objects else None

    if target is not None and target.name in context.view_layer.objects:
        context.view_layer.objects.active = target
        target.select_set(True)


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


classes: tuple[type[PropertyGroup], ...] = (
    LightListItem,
    LeoMoon_Light_Studio_Object_Properties,
)
