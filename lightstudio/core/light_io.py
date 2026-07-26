"""Per-light serialization round-trip (bpy-coupled).

Ports legacy ``light_data.salvage_data`` / ``light_data.light_from_dict``
plus ``common.getProfileHandle`` so the export/import operators in
:mod:`lightstudio.operators.profiles` can serialize lights to JSON and
restore them. The pure ``LightDict`` schema lives in
:mod:`lightstudio.core.light_data` (step 8).
"""

from __future__ import annotations

import contextlib
import os

import bpy

from .light_data import InvalidLight, LightDict
from .paths import TEXTURES_DIR
from .scene_utils import family, find_view_layer


def get_profile_handle(profile_obj: bpy.types.Object) -> bpy.types.Object | None:
    """Return the ``LLS_HANDLE`` child of a profile empty, or ``None``."""
    for h in profile_obj.children:
        if h.name.startswith("LLS_HANDLE"):
            return h
    return None


_GROUP_INPUT_KEYS = (
    "Texture Switch",
    "Color Overlay",
    "Color Saturation",
    "Desaturate",
    "Intensity",
    "Exposure",
    "Mask - Gradient Switch",
    "Mask - Gradient Type",
    "Mask - Gradient Amount",
    "Mask - Ring Switch",
    "Mask - Ring Inner Radius",
    "Mask - Ring Outer Radius",
    "Mask - Top to Bottom",
    "Mask - Bottom to Top",
    "Mask - Left to Right",
    "Mask - Right to Left",
    "Mask - Diagonal Top Left",
    "Mask - Diagonal Top Right",
    "Mask - Diagonal Bottom Right",
    "Mask - Diagonal Bottom Left",
    "Mask - Backface",
    "Mask - Grid Columns",
    "Mask - Grid Rows",
)

_INTEGER_GROUP_INPUT_KEYS = frozenset((
    "Mask - Grid Columns",
    "Mask - Grid Rows",
))


def salvage_data(
    lls_collection: bpy.types.Collection, only_validate: bool = False
) -> LightDict:
    """Walk an ``LLS_Light`` collection and serialize its state."""
    objects = list(lls_collection.objects)
    light_handle_candidates = [
        ob for ob in objects if ob.name.startswith("LLS_LIGHT.")
    ]
    if not light_handle_candidates:
        if only_validate:
            raise InvalidLight()
        return LightDict()
    light_group = light_handle_candidates[0]
    family_obs = family(light_group)

    lls_mesh = next(
        (ob for ob in family_obs if ob.name.startswith("LLS_LIGHT_MESH")), None
    )
    lls_basic = next(
        (ob for ob in family_obs if ob.name.startswith("LLS_LIGHT_AREA")), None
    )
    lls_handle = next(
        (ob for ob in family_obs if ob.name.startswith("LLS_LIGHT_HANDLE")),
        None,
    )

    light = LightDict()

    light_view = find_view_layer(
        lls_collection, bpy.context.view_layer.layer_collection
    )
    if light_view is not None:
        light["mute"] = bool(light_view.exclude)

    if lls_mesh is not None:
        try:
            light["light_name"] = lls_mesh.LLStudio.light_name
            light["order_index"] = lls_mesh.LLStudio.order_index
            light["radius"] = lls_mesh.location.x
            light["position"] = [
                lls_mesh.parent.rotation_euler.x,
                lls_mesh.parent.rotation_euler.y,
            ]
            light["rotation"] = -lls_mesh.rotation_euler.x
            light["type"] = "ADVANCED"
            light["visible_camera"] = lls_mesh.visible_camera
            light["scale"] = [
                lls_mesh.scale.y,
                lls_mesh.scale.x,
                lls_mesh.scale.z,
            ]
            mat = lls_mesh.material_slots[0].material
            tex_node = mat.node_tree.nodes["Light Texture"]
            tex_path = tex_node.image.filepath if tex_node.image else ""
            light["advanced"]["tex"] = tex_path.split(
                bpy.path.native_pathsep("\\textures_real_lights\\")
            )[-1]
            group = mat.node_tree.nodes["Group"]
            for key in _GROUP_INPUT_KEYS:
                try:
                    val = group.inputs[key].default_value
                    if hasattr(val, "__len__"):
                        light["advanced"][key] = list(val)
                    elif key in _INTEGER_GROUP_INPUT_KEYS:
                        light["advanced"][key] = int(round(float(val)))
                    else:
                        light["advanced"][key] = val
                except (KeyError, AttributeError):
                    if only_validate:
                        raise InvalidLight() from None
        except Exception:
            if only_validate:
                raise InvalidLight() from None

    if lls_handle is not None:
        try:
            light["light_name"] = lls_handle.LLStudio.light_name
            light["order_index"] = lls_handle.LLStudio.order_index
            light["radius"] = lls_handle.location.z
            light["position"] = [
                lls_handle.parent.rotation_euler.x,
                lls_handle.parent.rotation_euler.y,
            ]
            light["rotation"] = lls_handle.rotation_euler.y
            light["scale"] = list(lls_handle.scale[:])
            light["type"] = lls_handle.LLStudio.type
            _ = lls_handle.constraints["Child Of"].inverse_matrix
        except Exception:
            if only_validate:
                raise InvalidLight() from None

    if lls_basic is not None:
        try:
            light["basic"]["color"] = [
                lls_basic.data.LLStudio.color.r,
                lls_basic.data.LLStudio.color.g,
                lls_basic.data.LLStudio.color.b,
            ]
            light["basic"]["color_saturation"] = lls_basic.data.LLStudio.color_saturation
            light["basic"]["intensity"] = lls_basic.data.LLStudio.intensity
            light["visible_camera"] = lls_basic.visible_camera
        except Exception:
            if only_validate:
                raise InvalidLight() from None
    else:
        try:
            light["basic"]["color"] = light["advanced"]["Color Overlay"][:3]
            light["basic"]["color_saturation"] = light["advanced"]["Color Saturation"]
            light["basic"]["intensity"] = light["advanced"]["Intensity"]
        except Exception:
            if only_validate:
                raise InvalidLight() from None

    return light


_GROUP_INPUT_INDEX = {
    "Texture Switch": 2,
    "Color Overlay": 3,
    "Color Saturation": 4,
    "Desaturate": 5,
    "Intensity": 6,
    "Exposure": 7,
    "Mask - Gradient Switch": 8,
    "Mask - Gradient Type": 9,
    "Mask - Gradient Amount": 10,
    "Mask - Ring Switch": 11,
    "Mask - Ring Inner Radius": 12,
    "Mask - Ring Outer Radius": 13,
    "Mask - Top to Bottom": 14,
    "Mask - Bottom to Top": 15,
    "Mask - Left to Right": 16,
    "Mask - Right to Left": 17,
    "Mask - Diagonal Top Left": 18,
    "Mask - Diagonal Top Right": 19,
    "Mask - Diagonal Bottom Right": 20,
    "Mask - Diagonal Bottom Left": 21,
    "Mask - Backface": 22,
    "Mask - Grid Columns": 23,
    "Mask - Grid Rows": 24,
}


def light_from_dict(
    from_dict: dict | LightDict,
    profile_collection: bpy.types.Collection,
) -> None:
    """Materialize a serialized light back into a profile collection.

    Calls ``scene.add_leomoon_studio_light`` to create the hierarchy,
    then writes back every saved attribute (transforms, basic + advanced
    shader inputs, texture path).
    """
    if isinstance(from_dict, dict):
        light_dict = LightDict(from_dict)
        if "basic" not in from_dict:
            light_dict["basic"]["color"] = light_dict["advanced"]["Color Overlay"][:3]
            light_dict["basic"]["color_saturation"] = light_dict["advanced"][
                "Color Saturation"
            ]
            light_dict["basic"]["intensity"] = light_dict["advanced"]["Intensity"]
        if "order_index" not in from_dict:
            light_dict["order_index"] = None
    else:
        light_dict = from_dict

    profile_empty = next(
        ob
        for ob in profile_collection.objects
        if ob.name.startswith("LLS_PROFILE")
    )
    before = set(profile_empty.children)
    bpy.ops.scene.add_leomoon_studio_light()
    after = set(profile_empty.children)
    new_children = after - before
    if not new_children:
        return
    lgrp = new_children.pop()

    actuator = next(c for c in family(lgrp) if "LLS_ROTATION" in c.name)
    lhandle = next(c for c in family(lgrp) if "LLS_LIGHT_HANDLE" in c.name)
    ladvanced = next(c for c in family(lgrp) if "LLS_LIGHT_MESH" in c.name)
    lbasic = next(c for c in family(lgrp) if "LLS_LIGHT_AREA" in c.name)

    lhandle.location.z = light_dict["radius"]
    lhandle.rotation_euler.y = light_dict["rotation"]
    for c in lhandle.children:
        c.visible_camera = light_dict["visible_camera"]

    actuator.rotation_euler.x = light_dict["position"][0]
    actuator.rotation_euler.y = light_dict["position"][1]
    actuator.rotation_euler.z = 0

    lhandle.LLStudio.light_name = light_dict["light_name"]
    if light_dict["order_index"] is not None:
        lhandle.LLStudio.order_index = light_dict["order_index"]
    lhandle.scale = light_dict["scale"]

    # Force the basic-light data driver to flush.
    lhandle.LLStudio.type = "BASIC"
    with contextlib.suppress(RuntimeError):
        bpy.context.view_layer.objects.active = lbasic
    lbasic.data.LLStudio.color = light_dict["basic"]["color"]
    lbasic.data.LLStudio.color_saturation = light_dict["basic"]["color_saturation"]
    lbasic.data.LLStudio.intensity = light_dict["basic"]["intensity"]

    lhandle.LLStudio.type = light_dict["type"]

    # Advanced shader inputs.
    new_mat_nodes = ladvanced.material_slots[0].material.node_tree.nodes
    group = new_mat_nodes["Group"]
    advanced = light_dict["advanced"]
    for key, idx in _GROUP_INPUT_INDEX.items():
        if key not in advanced:
            continue
        val = advanced[key]
        try:
            if key in _INTEGER_GROUP_INPUT_KEYS:
                val = int(round(float(val)))
            socket = group.inputs.get(key) or group.inputs[idx]
            if hasattr(socket.default_value, "__len__"):
                for i, v in enumerate(val):
                    socket.default_value[i] = v
            else:
                socket.default_value = val
        except (IndexError, KeyError, TypeError):
            pass

    tex = advanced.get("tex", "")
    if tex:
        if os.path.isabs(tex):
            new_mat_nodes["Light Texture"].image.filepath = tex
        else:
            new_mat_nodes["Light Texture"].image.filepath = os.path.join(
                str(TEXTURES_DIR), tex
            )

    new_collection = next(
        (c for c in lgrp.users_collection if c.name.startswith("LLS")), None
    )
    if new_collection is not None:
        light_view = find_view_layer(
            new_collection, bpy.context.view_layer.layer_collection
        )
        if light_view is not None:
            light_view.exclude = bool(light_dict["mute"])
