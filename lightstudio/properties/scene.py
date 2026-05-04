"""Scene-level PropertyGroups for LeoMoon LightStudio.

Ported from ``LeoMoon_Light_Studio_Properties`` in legacy
``light_operators.py`` and ``ListItem`` in ``light_profiles.py``.

Update callbacks that drive multi-profile collection linking, light-list
view-layer toggles, and mode-change visibility cascades depend on
helpers that have not been ported yet (``check_profiles_consistency``,
``family``, view-layer walking). They are stubbed here with TODO
pointers and restored alongside the operators in steps 10-12. The
PropertyGroup *shape* (fields + types) matches the legacy add-on so
existing scenes continue to load.
"""

from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

from .object import LightListItem


def _profile_enabled_update(self: ListItem, context: bpy.types.Context) -> None:
    """Link/unlink the profile collection based on its enabled flag."""
    from ..core.scene_utils import (
        get_collection,
        get_lls_collection,
        update_light_list_set,
    )

    if self.empty_name not in bpy.data.objects:
        return
    profile_collection = get_collection(bpy.data.objects[self.empty_name])
    try:
        profile_list_index = int(self.path_from_id().split("[")[1].split("]")[0])
    except (IndexError, ValueError):
        profile_list_index = context.scene.LLStudio.profile_list_index

    lls_collection = get_lls_collection(context)
    if lls_collection is None:
        return
    if self.enabled:
        target = bpy.data.collections.get(self.empty_name)
        if target is not None and target.name not in lls_collection.children:
            lls_collection.children.link(target)
        update_light_list_set(context, profile_idx=profile_list_index)
    else:
        if (
            profile_collection is not None
            and profile_collection.name in lls_collection.children
        ):
            lls_collection.children.unlink(profile_collection)
        update_light_list_set(context)


class ListItem(PropertyGroup):
    """One entry in ``Scene.LLStudio.profile_list`` (drives the UIList)."""

    name: StringProperty(name="Profile Name", default="Untitled")
    empty_name: StringProperty(
        name="Name of Empty that holds the profile",
        description="",
        default="",
    )
    hash: StringProperty()
    enabled: BoolProperty(default=False, update=_profile_enabled_update)


def _profile_list_index_update(
    self: LeoMoon_Light_Studio_Properties, context: bpy.types.Context
) -> None:
    """Re-link the active profile and refresh the light list."""
    from ..core.profiles import update_profile_list_index

    update_profile_list_index(self, context)


def _multimode_refresh(
    self: LeoMoon_Light_Studio_Properties, context: bpy.types.Context
) -> None:
    """Repair profile-collection linking after a multimode toggle."""
    from ..core.profiles import check_profiles_consistency, update_profile_list_index

    check_profiles_consistency(context, invert_multimode=True)
    update_profile_list_index(self, context, multimode_override=True)


def _mode_change_func(self: LeoMoon_Light_Studio_Properties, context: bpy.types.Context) -> None:
    """Toggle visibility of light handles between NORMAL and ANIMATION modes."""
    from ..core.scene_utils import family

    if self.lls_mode == "NORMAL":
        roots = [
            o
            for o in context.scene.objects
            if o.name.startswith("LEOMOON_LIGHT_STUDIO")
        ]
        for root in roots:
            for elem in family(root):
                if "LLS_LIGHT_HANDLE" in elem.name:
                    elem.hide_viewport = True
                    elem.hide_select = True
    elif self.lls_mode == "ANIMATION":
        # Re-poke active object to fire the msgbus callback that unhides
        # the rotation + handle empties of the currently selected light.
        active = context.view_layer.objects.active
        context.view_layer.objects.active = active


def _light_list_index_get(self: LeoMoon_Light_Studio_Properties) -> int:
    """Return the list index matching the active object's LLS handle."""
    from ..core.scene_utils import is_family

    ob = bpy.context.view_layer.objects.active
    if not is_family(ob) or ob.parent is None:
        return -1
    parent_name = ob.parent.name
    for i, li in enumerate(self.light_list):
        if li.handle_name == parent_name:
            return i
    return -1


def _light_list_index_set(self: LeoMoon_Light_Studio_Properties, index: int) -> None:
    """Activate / select the light corresponding to ``index`` in the 3D view."""
    from ..core.scene_utils import find_view_layer

    if index < 0 or index >= len(self.light_list):
        return
    selected = self.light_list[index]
    light_handle = bpy.context.scene.objects.get(selected.handle_name)
    if light_handle is None or not light_handle.users_collection:
        return
    light_collection = light_handle.users_collection[0]
    light_layer = find_view_layer(
        light_collection, bpy.context.view_layer.layer_collection
    )
    if light_layer is None or light_layer.exclude:
        return

    bpy.ops.object.select_all(action="DESELECT")

    basic = next(
        (c for c in light_collection.children if c.name.startswith("LLS_Basic")),
        None,
    )
    advanced = next(
        (c for c in light_collection.children if c.name.startswith("LLS_Advanced")),
        None,
    )
    if basic is None or advanced is None:
        return
    basic_view = find_view_layer(basic, bpy.context.view_layer.layer_collection)
    advanced_view = find_view_layer(
        advanced, bpy.context.view_layer.layer_collection
    )
    if basic_view is None or advanced_view is None:
        return

    if int(basic_view.exclude) + int(advanced_view.exclude) != 1:
        advanced_view.exclude = False
        basic_view.exclude = True

    if not basic_view.exclude and basic.objects:
        light_object = basic.objects[0]
    elif not advanced_view.exclude and advanced.objects:
        light_object = advanced.objects[0]
    else:
        return

    if light_object.name in bpy.context.view_layer.objects:
        bpy.context.view_layer.objects.active = light_object
        light_object.select_set(True)


class LeoMoon_Light_Studio_Properties(PropertyGroup):
    """Top-level LLS state attached to ``Scene.LLStudio``."""

    initialized: BoolProperty(default=False)

    profile_list: CollectionProperty(type=ListItem)
    profile_list_index: IntProperty(
        name="Index for profile_list",
        default=0,
        update=_profile_list_index_update,
    )
    last_empty: StringProperty(
        name="Name of last Empty holding profile",
        default="",
    )
    profile_multimode: BoolProperty(
        default=False,
        name="Multi Profile Mode",
        description="Use many profiles at once.",
        update=_multimode_refresh,
    )

    light_list: CollectionProperty(type=LightListItem)
    light_list_index: IntProperty(
        name="Index for light_list",
        default=0,
        get=_light_list_index_get,
        set=_light_list_index_set,
    )

    lls_mode: EnumProperty(
        items=[
            ("NORMAL", "Normal", "Normal"),
            ("ANIMATION", "Animation", "Animation"),
        ],
        name="Mode",
        description="Use Animated mode to select all light components for easier keyframe editing.",
        update=_mode_change_func,
        default="NORMAL",
    )


classes: tuple[type[PropertyGroup], ...] = (
    ListItem,
    LeoMoon_Light_Studio_Properties,
)
