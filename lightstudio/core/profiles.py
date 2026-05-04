"""Profile lifecycle helpers (bpy-coupled).

Ported from legacy ``light_profiles`` and the parts of ``light_list``
that drive profile-collection linking. These helpers are kept in
``core`` (rather than directly in the operators module) so the property
update callbacks in :mod:`lightstudio.properties.scene` can call them
without creating an operator-package import cycle.
"""

from __future__ import annotations

import random
from time import time_ns

import bpy

from .scene_utils import (
    duplicate_collection,
    find_view_layer,
    get_collection,
    get_lls_collection,
    update_light_list_set,
)

_PROFILE_NAME_PREFIX = "LLS_PROFILE"
_LIGHT_HANDLE_PREFIX = "LLS_LIGHT_HANDLE"


def get_hash() -> str:
    """Generate a unique hash used to detect duplicated profiles."""
    return str(time_ns()) + "".join(
        random.choice("0123456789ABCDEFGHIJKLMNOPRSTUWXYZ") for _ in range(4)
    )


def add_profile_hashes() -> None:
    """Backfill missing ``hash`` properties on every known profile."""
    scene_profiles = {
        profile
        for scene in bpy.data.scenes
        for profile in scene.LLStudio.profile_list
    }
    for profile in scene_profiles:
        try:
            profile_root = bpy.data.objects[profile.empty_name]
            if not profile.hash or "hash" not in profile_root:
                h = get_hash()
                profile.hash = h
                profile_root["hash"] = h
        except Exception:  # noqa: BLE001 - malformed legacy data is tolerated
            pass


def _lls_root(scene: bpy.types.Scene) -> bpy.types.Object | None:
    for o in scene.objects:
        if o.name.startswith("LEOMOON_LIGHT_STUDIO"):
            return o
    return None


def check_profiles_consistency(
    context: bpy.types.Context, invert_multimode: bool = False
) -> bool:
    """Re-link the profile list when the active scene was duplicated.

    Returns ``True`` if any list-item was repaired.
    """
    list_props = context.scene.LLStudio
    scene_profile_list = list_props.profile_list
    if not len(scene_profile_list):
        return False

    profile_menu_item = scene_profile_list[list_props.profile_list_index]
    profile_empty_idx = bpy.data.objects.find(profile_menu_item.empty_name)
    lls_root = _lls_root(context.scene)
    if lls_root is None:
        return False

    changed = False
    multimode = list_props.profile_multimode
    single_mode_branch = (not invert_multimode and not multimode) or (
        invert_multimode and multimode
    )

    if single_mode_branch:
        if profile_empty_idx == -1:
            return False
        try:
            this_scene_profiles = (
                o
                for o in lls_root.children
                if o.name.startswith(_PROFILE_NAME_PREFIX)
                and o.name in context.scene.objects
            )
            this_profile_root = next(this_scene_profiles)
            if this_profile_root.name != profile_menu_item.empty_name:
                profile_menu_item.empty_name = this_profile_root.name
                h = get_hash()
                profile_menu_item.hash = h
                this_profile_root["hash"] = h
                changed = True

                # Scene was duplicated: rebuild every other profile from
                # an independent copy of its (still-original) collection.
                for prof in scene_profile_list:
                    if prof == profile_menu_item:
                        continue
                    try:
                        prof_collection = get_collection(
                            bpy.data.objects[prof.empty_name]
                        )
                    except KeyError:
                        continue
                    if prof_collection is None:
                        continue
                    col = duplicate_collection(prof_collection, None)
                    new_root = next(
                        ob
                        for ob in col.objects
                        if ob.name.startswith(_PROFILE_NAME_PREFIX)
                    )
                    prof.empty_name = new_root.name
                    h = get_hash()
                    prof.hash = h
                    new_root["hash"] = h
                    changed = True
        except (StopIteration, KeyError) as exc:
            print(
                "Something wrong with object hierarchy. "
                "Profile consistency check failed.",
                exc,
            )
        return changed

    # Multimode branch.
    try:
        enabled = [p for p in scene_profile_list if p.enabled]
        disabled = [p for p in scene_profile_list if not p.enabled]
        duped = False
        for prof in enabled:
            this_scene_profiles = (
                o
                for o in lls_root.children
                if o.name.startswith(_PROFILE_NAME_PREFIX)
                and o.name in context.scene.objects
                and "hash" in o
                and o["hash"] == prof.hash
            )
            this_profile_root = next(this_scene_profiles)
            if this_profile_root.name != prof.empty_name:
                prof.empty_name = this_profile_root.name
                h = get_hash()
                prof.hash = h
                this_profile_root["hash"] = h
                changed = duped = True
        if duped:
            for prof in disabled:
                try:
                    prof_collection = get_collection(
                        bpy.data.objects[prof.empty_name]
                    )
                except KeyError:
                    continue
                if prof_collection is None:
                    continue
                col = duplicate_collection(prof_collection, None)
                new_root = next(
                    ob
                    for ob in col.objects
                    if ob.name.startswith(_PROFILE_NAME_PREFIX)
                )
                prof.empty_name = new_root.name
                h = get_hash()
                prof.hash = h
                new_root["hash"] = h
    except (StopIteration, KeyError) as exc:
        print(
            "Something wrong with object hierarchy. "
            "Multi-Profile consistency check failed.",
            exc,
        )
    return changed


def update_profile_list_index(
    props: bpy.types.PropertyGroup,
    context: bpy.types.Context,
    multimode_override: bool = False,
) -> None:
    """Re-link the active profile collection and refresh the light list."""
    if len(props.profile_list) == 0 or props.profile_list_index >= len(
        props.profile_list
    ):
        return

    selected_profile = props.profile_list[props.profile_list_index]
    if selected_profile.empty_name not in bpy.data.collections:
        # Stale list item — drop it.
        props.profile_list.remove(props.profile_list_index)
        return

    if not multimode_override and selected_profile.empty_name == props.last_empty:
        return

    if not props.profile_multimode:
        lls_collection = get_lls_collection(context)
        if lls_collection is not None:
            profile_collections = [
                c
                for c in lls_collection.children
                if c.name.startswith(_PROFILE_NAME_PREFIX)
            ]
            for col in profile_collections:
                lls_collection.children.unlink(col)
            new_profile_collection = bpy.data.collections.get(
                selected_profile.empty_name
            )
            if new_profile_collection is not None:
                lls_collection.children.link(new_profile_collection)
                # restore lights' visibility
                for col in new_profile_collection.children:
                    light_handle = next(
                        (
                            o
                            for o in col.objects
                            if o.name.startswith(_LIGHT_HANDLE_PREFIX)
                        ),
                        None,
                    )
                    if light_handle is None:
                        continue
                    if light_handle.LLStudio.mute:
                        layer = find_view_layer(
                            col, context.view_layer.layer_collection
                        )
                        if layer is not None:
                            layer.exclude = light_handle.LLStudio.mute

    props.last_empty = selected_profile.empty_name

    # Notify modal control panel.
    from ..operators.modal.control_panel import panel_global, update_light_sets
    if panel_global:
        update_light_sets(panel_global, bpy.context, always=True)

    update_light_list_set(context)
