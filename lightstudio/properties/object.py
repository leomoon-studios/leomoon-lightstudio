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
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

_INTEGER_INPUT_NAMES = {
    "mask_gradient_switch": "Mask - Gradient Switch",
    "mask_ring_switch": "Mask - Ring Switch",
    "mask_backface": "Mask - Backface",
    "mask_grid_columns": "Mask - Grid Columns",
    "mask_grid_rows": "Mask - Grid Rows",
}

_BINARY_INPUT_PROPS = {
    "mask_gradient_switch",
    "mask_ring_switch",
    "mask_backface",
}


def _animation_owner_update(
    self: LeoMoon_Light_Studio_Object_Properties,
    context: bpy.types.Context,
) -> None:
    from ..core.light_animation import sync_from_emitter

    obj = self.id_data
    if isinstance(obj, bpy.types.Object):
        sync_from_emitter(obj)


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
    socket_name = _INTEGER_INPUT_NAMES[prop_name]
    try:
        socket = obj.active_material.node_tree.nodes["Group"].inputs[socket_name]
        if prop_name in _BINARY_INPUT_PROPS:
            return 1 if float(socket.default_value) > 0 else 0
        return int(round(socket.default_value))
    except (AttributeError, KeyError, TypeError, ValueError):
        return 0


def _grid_input_set(
    self: LeoMoon_Light_Studio_Object_Properties, prop_name: str, value: int
) -> None:
    obj = self.id_data
    socket_name = _INTEGER_INPUT_NAMES[prop_name]
    try:
        socket = obj.active_material.node_tree.nodes["Group"].inputs[socket_name]
        if prop_name in _BINARY_INPUT_PROPS:
            socket.default_value = 1 if int(value) > 0 else 0
        else:
            socket.default_value = int(value)
    except (AttributeError, KeyError, TypeError, ValueError):
        return


def _mask_gradient_switch_get(self: LeoMoon_Light_Studio_Object_Properties) -> int:
    return _grid_input_get(self, "mask_gradient_switch")


def _mask_gradient_switch_set(
    self: LeoMoon_Light_Studio_Object_Properties, value: int
) -> None:
    _grid_input_set(self, "mask_gradient_switch", value)


def _mask_ring_switch_get(self: LeoMoon_Light_Studio_Object_Properties) -> int:
    return _grid_input_get(self, "mask_ring_switch")


def _mask_ring_switch_set(
    self: LeoMoon_Light_Studio_Object_Properties, value: int
) -> None:
    _grid_input_set(self, "mask_ring_switch", value)


def _mask_backface_get(self: LeoMoon_Light_Studio_Object_Properties) -> int:
    return _grid_input_get(self, "mask_backface")


def _mask_backface_set(
    self: LeoMoon_Light_Studio_Object_Properties, value: int
) -> None:
    _grid_input_set(self, "mask_backface", value)


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
    mask_gradient_switch: IntProperty(
        name="Mask - Gradient Switch",
        min=0,
        max=1,
        default=0,
        get=_mask_gradient_switch_get,
        set=_mask_gradient_switch_set,
    )
    mask_ring_switch: IntProperty(
        name="Mask - Ring Switch",
        min=0,
        max=1,
        default=0,
        get=_mask_ring_switch_get,
        set=_mask_ring_switch_set,
    )
    mask_backface: IntProperty(
        name="Mask - Backface",
        min=0,
        max=1,
        default=0,
        get=_mask_backface_get,
        set=_mask_backface_set,
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

    anim_owner_initialized: BoolProperty(default=False)
    anim_distance: FloatProperty(
        name="Distance",
        min=0.0,
        default=30.0,
        update=_animation_owner_update,
    )
    anim_position_x: FloatProperty(
        name="Position X",
        update=_animation_owner_update,
    )
    anim_position_y: FloatProperty(
        name="Position Y",
        update=_animation_owner_update,
    )
    anim_rotation: FloatProperty(
        name="Rotation",
        update=_animation_owner_update,
    )
    anim_scale_x: FloatProperty(
        name="Scale X",
        default=1.0,
        update=_animation_owner_update,
    )
    anim_scale_y: FloatProperty(
        name="Scale Y",
        default=1.0,
        update=_animation_owner_update,
    )
    anim_scale_z: FloatProperty(
        name="Scale Z",
        default=1.0,
        update=_animation_owner_update,
    )

    adv_texture_switch: FloatProperty(
        name="Texture Switch",
        default=1.0,
        update=_animation_owner_update,
    )
    adv_color_saturation: FloatProperty(
        name="Color Saturation",
        min=0.0,
        max=1.0,
        update=_animation_owner_update,
    )
    adv_desaturate: FloatProperty(
        name="Desaturate",
        min=0.0,
        max=1.0,
        update=_animation_owner_update,
    )
    adv_color_overlay: FloatVectorProperty(
        name="Color Overlay",
        subtype="COLOR",
        size=4,
        default=(1.0, 0.5, 0.25, 1.0),
        soft_min=0.0,
        soft_max=1.0,
        update=_animation_owner_update,
    )
    adv_intensity: FloatProperty(
        name="Intensity",
        default=2.0,
        soft_min=0.0,
        soft_max=10000.0,
        update=_animation_owner_update,
    )
    adv_exposure: FloatProperty(
        name="Exposure",
        default=1.0,
        update=_animation_owner_update,
    )
    adv_mask_gradient_type: FloatProperty(
        name="Mask - Gradient Type",
        update=_animation_owner_update,
    )
    adv_mask_gradient_amount: FloatProperty(
        name="Mask - Gradient Amount",
        update=_animation_owner_update,
    )
    adv_mask_ring_inner_radius: FloatProperty(
        name="Mask - Ring Inner Radius",
        update=_animation_owner_update,
    )
    adv_mask_ring_outer_radius: FloatProperty(
        name="Mask - Ring Outer Radius",
        update=_animation_owner_update,
    )
    adv_mask_top_to_bottom: FloatProperty(
        name="Mask - Top to Bottom",
        update=_animation_owner_update,
    )
    adv_mask_bottom_to_top: FloatProperty(
        name="Mask - Bottom to Top",
        update=_animation_owner_update,
    )
    adv_mask_left_to_right: FloatProperty(
        name="Mask - Left to Right",
        update=_animation_owner_update,
    )
    adv_mask_right_to_left: FloatProperty(
        name="Mask - Right to Left",
        update=_animation_owner_update,
    )
    adv_mask_diagonal_top_left: FloatProperty(
        name="Mask - Diagonal Top Left",
        update=_animation_owner_update,
    )
    adv_mask_diagonal_top_right: FloatProperty(
        name="Mask - Diagonal Top Right",
        update=_animation_owner_update,
    )
    adv_mask_diagonal_bottom_right: FloatProperty(
        name="Mask - Diagonal Bottom Right",
        update=_animation_owner_update,
    )
    adv_mask_diagonal_bottom_left: FloatProperty(
        name="Mask - Diagonal Bottom Left",
        update=_animation_owner_update,
    )

    basic_color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        default=(1.0, 1.0, 1.0),
        size=3,
        soft_min=0.0,
        soft_max=1.0,
        update=_animation_owner_update,
    )
    basic_color_saturation: FloatProperty(
        name="Color Saturation",
        min=0.0,
        max=1.0,
        update=_animation_owner_update,
    )
    basic_intensity: FloatProperty(
        name="Intensity",
        soft_min=0.0,
        soft_max=10000.0,
        default=2.0,
        update=_animation_owner_update,
    )


classes: tuple[type[PropertyGroup], ...] = (
    LightListItem,
    LightLinkingTargetItem,
    LeoMoon_Light_Studio_Object_Properties,
)
