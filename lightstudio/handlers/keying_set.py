"""LightStudio keying set (Step 17).

Ports ``BUILTIN_KSI_LightStudio`` (a :class:`bpy.types.KeyingSetInfo`)
plus the ``lls.lls_keyingset`` activation operator from legacy
``light_operators.py`` / ``gui.py``.

The keying set stores transform keys on the visible Basic/Advanced
light objects, then frame handlers push those evaluated values back to
the hidden LightStudio rig.
"""

from __future__ import annotations

import contextlib

import bpy

from ..core.light_animation import (
    TRANSFORM_PROPS,
    active_emitter_for_handle,
    ensure_shared_action,
    sync_emitters_from_rig,
)
from ..core.scene_utils import family, find_light_grp

_KSI_BL_IDNAME = "BUILTIN_KSI_LightStudio"
_TRANSFORM_PATHS = tuple(f"LLStudio.{prop_name}" for prop_name in TRANSFORM_PROPS)


class BUILTIN_KSI_LightStudio(bpy.types.KeyingSetInfo):
    bl_label = "LightStudio KeyingSet"

    def poll(ksi, context):  # noqa: N805 - Blender API
        scene = context.scene
        props = getattr(scene, "LLStudio", None)
        if props is None or not props.initialized:
            return False
        return bool(context.active_object or context.selected_objects)

    def iterator(ksi, context, ks):  # noqa: N805
        for ob in (
            o
            for o in context.selected_objects
            if o.name.startswith("LLS_LIGHT")
        ):
            ksi.generate(context, ks, ob)

    def generate(ksi, context, ks, data):  # noqa: N805
        id_block = data.id_data
        lls_root = find_light_grp(id_block)
        if lls_root is None:
            return
        if id_block.name.startswith(("LLS_LIGHT_MESH", "LLS_LIGHT_AREA")):
            emitter = id_block
        else:
            handle = next(
                (
                    m
                    for m in family(lls_root)
                    if m.name.startswith("LLS_LIGHT_HANDLE")
                ),
                None,
            )
            emitter = active_emitter_for_handle(handle)
        if emitter is None:
            return
        for data_path in _TRANSFORM_PATHS:
            ks.paths.add(emitter, data_path, group_method="KEYINGSET")


class LLS_OT_KeyingSet(bpy.types.Operator):
    bl_idname = "lls.lls_keyingset"
    bl_label = "LightStudio Keying Set"
    bl_description = "Activate LightStudio Keying Set to animate lights"
    bl_options = {"INTERNAL", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        props = getattr(scene, "LLStudio", None) if scene else None
        return bool(props and len(props.profile_list))

    def execute(self, context):
        matches = [
            k
            for k in context.scene.keying_sets_all
            if k.bl_idname == _KSI_BL_IDNAME
        ]
        if not matches:
            self.report({"WARNING"}, "LightStudio keying set not registered")
            return {"CANCELLED"}
        context.scene.keying_sets.active = matches[0]
        return {"FINISHED"}


def _selected_lls_handles(context):
    """Return the LLS handles reachable from the current selection."""
    handles: list[bpy.types.Object] = []
    seen: set[str] = set()
    for obj in context.selected_objects or ():
        root = find_light_grp(obj)
        if root is None:
            continue
        for member in family(root):
            if (
                member.name.startswith("LLS_LIGHT_HANDLE")
                and member.name not in seen
            ):
                handles.append(member)
                seen.add(member.name)
    return handles


def _emitter_for_handle_and_selection(
    handle: bpy.types.Object,
    context: bpy.types.Context,
) -> bpy.types.Object | None:
    for obj in context.selected_objects or ():
        if not obj.name.startswith(("LLS_LIGHT_MESH", "LLS_LIGHT_AREA")):
            continue
        if find_light_grp(obj) == find_light_grp(handle):
            return obj
    return active_emitter_for_handle(handle)


class LLS_OT_InsertKeyActiveLight(bpy.types.Operator):
    bl_idname = "lls.insert_key_active_light"
    bl_label = "Insert Key for Active Light"
    bl_description = (
        "Insert a keyframe on the selected LightStudio light(s) using the "
        "LightStudio Keying Set"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        props = getattr(scene, "LLStudio", None) if scene else None
        if not props or not props.initialized:
            return False
        return bool(_selected_lls_handles(context))

    def execute(self, context):
        scene = context.scene
        matches = [
            k
            for k in scene.keying_sets_all
            if k.bl_idname == _KSI_BL_IDNAME
        ]
        if not matches:
            self.report({"WARNING"}, "LightStudio keying set not registered")
            return {"CANCELLED"}

        keyed = 0
        frame = scene.frame_current
        for handle in _selected_lls_handles(context):
            sync_emitters_from_rig(handle)
            ensure_shared_action(handle)
            emitter = _emitter_for_handle_and_selection(handle, context)
            if emitter is None:
                continue
            for data_path in _TRANSFORM_PATHS:
                if emitter.keyframe_insert(data_path=data_path, frame=frame):
                    keyed += 1

        if keyed == 0:
            self.report({"WARNING"}, "Nothing was keyed")
            return {"CANCELLED"}

        count = len(_selected_lls_handles(context))
        self.report(
            {"INFO"},
            f"Keyed {count} LightStudio light{'s' if count != 1 else ''} "
            f"@ frame {scene.frame_current}",
        )
        return {"FINISHED"}


classes: tuple[type, ...] = (
    BUILTIN_KSI_LightStudio,
    LLS_OT_KeyingSet,
    LLS_OT_InsertKeyActiveLight,
)


def register() -> None:
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(classes):
        with contextlib.suppress(RuntimeError):
            bpy.utils.unregister_class(cls)
