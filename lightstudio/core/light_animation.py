"""Animation ownership helpers for LightStudio lights."""

from __future__ import annotations

import contextlib

import bpy
from mathutils import Vector

from .scene_utils import family, find_light_grp

_SYNCING = False

TRANSFORM_PROPS = (
    "anim_distance",
    "anim_position_x",
    "anim_position_y",
    "anim_rotation",
    "anim_scale_x",
    "anim_scale_y",
    "anim_scale_z",
)

ADVANCED_FLOAT_INPUT_NAMES = {
    "adv_texture_switch": "Texture Switch",
    "adv_color_saturation": "Color Saturation",
    "adv_desaturate": "Desaturate",
    "adv_intensity": "Intensity",
    "adv_exposure": "Exposure",
    "adv_mask_gradient_type": "Mask - Gradient Type",
    "adv_mask_gradient_amount": "Mask - Gradient Amount",
    "adv_mask_ring_inner_radius": "Mask - Ring Inner Radius",
    "adv_mask_ring_outer_radius": "Mask - Ring Outer Radius",
    "adv_mask_top_to_bottom": "Mask - Top to Bottom",
    "adv_mask_bottom_to_top": "Mask - Bottom to Top",
    "adv_mask_left_to_right": "Mask - Left to Right",
    "adv_mask_right_to_left": "Mask - Right to Left",
    "adv_mask_diagonal_top_left": "Mask - Diagonal Top Left",
    "adv_mask_diagonal_top_right": "Mask - Diagonal Top Right",
    "adv_mask_diagonal_bottom_right": "Mask - Diagonal Bottom Right",
    "adv_mask_diagonal_bottom_left": "Mask - Diagonal Bottom Left",
}

ADVANCED_VECTOR_INPUT_NAMES = {
    "adv_color_overlay": "Color Overlay",
}

BASIC_PROPS = ("basic_color", "basic_color_saturation", "basic_intensity")
ACTION_PREFIX = "LLS_LIGHT_ANIM"


def is_syncing() -> bool:
    return _SYNCING


@contextlib.contextmanager
def sync_guard():
    global _SYNCING
    was_syncing = _SYNCING
    _SYNCING = True
    try:
        yield
    finally:
        _SYNCING = was_syncing


def light_members(obj: bpy.types.Object | None):
    if obj is None:
        return None, None, None, None
    root = find_light_grp(obj)
    if root is None and obj.name.startswith("LLS_LIGHT."):
        root = obj
    if root is None:
        return None, None, None, None
    members = family(root)
    handle = next((m for m in members if m.name.startswith("LLS_LIGHT_HANDLE")), None)
    advanced = next((m for m in members if m.name.startswith("LLS_LIGHT_MESH")), None)
    basic = next((m for m in members if m.name.startswith("LLS_LIGHT_AREA")), None)
    return root, handle, advanced, basic


def light_emitters(obj: bpy.types.Object | None) -> tuple[bpy.types.Object, ...]:
    _root, _handle, advanced, basic = light_members(obj)
    return tuple(o for o in (advanced, basic) if o is not None)


def ensure_shared_action(obj: bpy.types.Object | None) -> bpy.types.Action | None:
    """Assign one Action and one Action slot to both visible emitters."""
    _root, handle, advanced, basic = light_members(obj)
    if handle is None:
        return None
    emitters = tuple(o for o in (advanced, basic) if o is not None)
    if not emitters:
        return None

    action_name = f"{ACTION_PREFIX}.{handle.name}"
    action = bpy.data.actions.get(action_name)
    if action is None:
        action = next(
            (
                emitter.animation_data.action
                for emitter in emitters
                if emitter.animation_data and emitter.animation_data.action
            ),
            None,
        )
    if action is None:
        action = bpy.data.actions.new(action_name)
    action.name = action_name
    action.use_fake_user = True

    slot = next(
        (
            emitter.animation_data.action_slot
            for emitter in emitters
            if emitter.animation_data
            and emitter.animation_data.action == action
            and emitter.animation_data.action_slot is not None
        ),
        None,
    )
    if slot is None:
        slot = next(iter(getattr(action, "slots", ()) or ()), None)
    if slot is None:
        label = handle.LLStudio.light_name or handle.name
        slot = action.slots.new("OBJECT", label)

    for emitter in emitters:
        anim = emitter.animation_data_create()
        anim.action = action
        with contextlib.suppress(TypeError, AttributeError, RuntimeError):
            anim.action_slot = slot
    return action


def active_emitter_for_handle(handle: bpy.types.Object | None) -> bpy.types.Object | None:
    if handle is None:
        return None
    _root, _rig, advanced, basic = light_members(handle)
    return basic if handle.LLStudio.type == "BASIC" else advanced


def _advanced_group_inputs(advanced: bpy.types.Object | None):
    try:
        return advanced.active_material.node_tree.nodes["Group"].inputs
    except (AttributeError, KeyError, TypeError):
        return None


def _action_data_paths(id_block: bpy.types.ID | None) -> set[str]:
    anim = getattr(id_block, "animation_data", None)
    action = getattr(anim, "action", None) if anim is not None else None
    if action is None:
        return set()

    fcurves = getattr(action, "fcurves", None)
    if fcurves is not None:
        return {fcurve.data_path for fcurve in fcurves}

    paths: set[str] = set()
    slots = tuple(getattr(action, "slots", ()) or ())
    for layer in getattr(action, "layers", ()) or ():
        for strip in getattr(layer, "strips", ()) or ():
            channelbags = getattr(strip, "channelbags", None)
            if channelbags is not None:
                for bag in channelbags:
                    paths.update(fcurve.data_path for fcurve in bag.fcurves)
                continue
            channelbag = getattr(strip, "channelbag", None)
            if not callable(channelbag):
                continue
            for slot in slots:
                with contextlib.suppress(Exception):
                    bag = channelbag(slot)
                    if bag is not None:
                        paths.update(fcurve.data_path for fcurve in bag.fcurves)
    return paths


def _has_paths(id_block: bpy.types.ID | None, paths: set[str]) -> bool:
    return bool(_action_data_paths(id_block) & paths)


def has_emitter_transform_animation(emitter: bpy.types.Object | None) -> bool:
    paths = {f"LLStudio.{prop_name}" for prop_name in TRANSFORM_PROPS}
    return _has_paths(emitter, paths)


def has_emitter_option_animation(emitter: bpy.types.Object | None) -> bool:
    paths = {
        *(f"LLStudio.{prop_name}" for prop_name in ADVANCED_FLOAT_INPUT_NAMES),
        *(f"LLStudio.{prop_name}" for prop_name in ADVANCED_VECTOR_INPUT_NAMES),
        *(f"LLStudio.{prop_name}" for prop_name in BASIC_PROPS),
    }
    return _has_paths(emitter, paths)


def _set_emitter_prop(emitter: bpy.types.Object, prop_name: str, value) -> None:
    with contextlib.suppress(AttributeError, TypeError, ValueError):
        setattr(emitter.LLStudio, prop_name, value)


def sync_emitters_from_rig(obj: bpy.types.Object | None) -> None:
    """Copy the hidden rig transform and real option values onto emitters."""
    _root, handle, advanced, basic = light_members(obj)
    if handle is None:
        return
    actuator = handle.parent
    emitters = tuple(o for o in (advanced, basic) if o is not None)
    if not emitters:
        return

    with sync_guard():
        for emitter in emitters:
            emitter.LLStudio.anim_distance = handle.location.z
            emitter.LLStudio.anim_rotation = handle.rotation_euler.y
            emitter.LLStudio.anim_scale_x = handle.scale.x
            emitter.LLStudio.anim_scale_y = handle.scale.y
            emitter.LLStudio.anim_scale_z = handle.scale.z
            emitter.LLStudio.anim_owner_initialized = True
            if actuator is not None:
                emitter.LLStudio.anim_position_x = actuator.rotation_euler.x
                emitter.LLStudio.anim_position_y = actuator.rotation_euler.y

        inputs = _advanced_group_inputs(advanced)
        if inputs is not None:
            for prop_name, socket_name in ADVANCED_FLOAT_INPUT_NAMES.items():
                with contextlib.suppress(KeyError, TypeError, ValueError):
                    value = float(inputs[socket_name].default_value)
                    for emitter in emitters:
                        _set_emitter_prop(emitter, prop_name, value)
            for prop_name, socket_name in ADVANCED_VECTOR_INPUT_NAMES.items():
                with contextlib.suppress(KeyError, TypeError, ValueError):
                    value = tuple(inputs[socket_name].default_value)
                    for emitter in emitters:
                        _set_emitter_prop(emitter, prop_name, value)

        if basic is not None and getattr(basic, "data", None) is not None:
            light_props = getattr(basic.data, "LLStudio", None)
            if light_props is not None:
                for emitter in emitters:
                    emitter.LLStudio.basic_color = light_props.color
                    emitter.LLStudio.basic_color_saturation = light_props.color_saturation
                    emitter.LLStudio.basic_intensity = light_props.intensity


def sync_rig_from_emitter(emitter: bpy.types.Object | None) -> None:
    """Apply an emitter's animated transform properties to the hidden rig."""
    _root, handle, _advanced, _basic = light_members(emitter)
    if emitter is None or handle is None:
        return
    actuator = handle.parent
    props = emitter.LLStudio
    with sync_guard():
        handle.location.z = props.anim_distance
        handle.rotation_euler.y = props.anim_rotation
        handle.scale = (
            props.anim_scale_x,
            props.anim_scale_y,
            props.anim_scale_z,
        )
        if actuator is not None:
            actuator.rotation_euler.x = props.anim_position_x
            actuator.rotation_euler.y = props.anim_position_y


def sync_options_from_emitter(emitter: bpy.types.Object | None) -> None:
    """Apply an emitter's animated option properties to real render owners."""
    _root, _handle, advanced, basic = light_members(emitter)
    if emitter is None:
        return
    props = emitter.LLStudio
    with sync_guard():
        inputs = _advanced_group_inputs(advanced)
        if inputs is not None:
            for prop_name, socket_name in ADVANCED_FLOAT_INPUT_NAMES.items():
                with contextlib.suppress(KeyError, TypeError, ValueError):
                    inputs[socket_name].default_value = getattr(props, prop_name)
            for prop_name, socket_name in ADVANCED_VECTOR_INPUT_NAMES.items():
                with contextlib.suppress(KeyError, TypeError, ValueError):
                    inputs[socket_name].default_value = getattr(props, prop_name)

        if basic is not None and getattr(basic, "data", None) is not None:
            light_props = getattr(basic.data, "LLStudio", None)
            if light_props is not None:
                color = Vector(props.basic_color)
                saturation = props.basic_color_saturation
                intensity = props.basic_intensity
                light_props.color = color
                light_props.color_saturation = saturation
                light_props.intensity = intensity
                basic.data.color = Vector((1.0, 1.0, 1.0)).lerp(color, saturation)
                try:
                    parent = basic.parent
                    basic.data.energy = intensity * parent.scale.x * parent.scale.z * 250
                except (AttributeError, TypeError):
                    basic.data.energy = intensity


def sync_counterpart_from_emitter(emitter: bpy.types.Object | None) -> None:
    """Copy visible animation-owner values to the sibling emitter."""
    emitters = light_emitters(emitter)
    if emitter is None or len(emitters) < 2:
        return
    source_props = emitter.LLStudio
    with sync_guard():
        for other in emitters:
            if other == emitter:
                continue
            for prop_name in (
                *TRANSFORM_PROPS,
                *ADVANCED_FLOAT_INPUT_NAMES.keys(),
                *ADVANCED_VECTOR_INPUT_NAMES.keys(),
                *BASIC_PROPS,
            ):
                _set_emitter_prop(other, prop_name, getattr(source_props, prop_name))


def sync_from_emitter(emitter: bpy.types.Object | None) -> None:
    if is_syncing():
        return
    sync_rig_from_emitter(emitter)
    sync_options_from_emitter(emitter)
    sync_counterpart_from_emitter(emitter)


def sync_scene_animation(scene: bpy.types.Scene) -> None:
    """Push evaluated visible-emitter animation values into real rig/render owners."""
    props = getattr(scene, "LLStudio", None)
    if props is None or not props.initialized:
        return
    for item in props.light_list:
        handle = bpy.data.objects.get(item.handle_name)
        emitter = active_emitter_for_handle(handle)
        if emitter is not None:
            if not getattr(emitter.LLStudio, "anim_owner_initialized", False):
                sync_emitters_from_rig(handle)
                continue
            if has_emitter_transform_animation(emitter):
                sync_rig_from_emitter(emitter)
            if has_emitter_option_animation(emitter):
                sync_options_from_emitter(emitter)
