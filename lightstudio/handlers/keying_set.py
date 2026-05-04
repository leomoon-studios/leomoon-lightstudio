"""LightStudio keying set (Step 17).

Ports ``BUILTIN_KSI_LightStudio`` (a :class:`bpy.types.KeyingSetInfo`)
plus the ``lls.lls_keyingset`` activation operator from legacy
``light_operators.py`` / ``gui.py``.

The keying set adds the LLS handle's ``location.z`` /
``rotation_euler.y`` / ``scale`` and the actuator's ``rotation_euler``
to the active keying set, so a single ``I`` keys every LLS-controllable
parameter on the selected lights.
"""

from __future__ import annotations

import contextlib

import bpy

from ..core.scene_utils import family, find_light_grp

_KSI_BL_IDNAME = "BUILTIN_KSI_LightStudio"


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
        family_obs = family(lls_root)
        handles = [m for m in family_obs if m.name.startswith("LLS_LIGHT_HANDLE")]
        if not handles:
            return
        lls_handle = handles[0]
        lls_actuator = lls_handle.parent
        ks.paths.add(lls_handle, "location", index=2, group_method="KEYINGSET")
        ks.paths.add(
            lls_handle, "rotation_euler", index=1, group_method="KEYINGSET"
        )
        ks.paths.add(lls_handle, "scale", group_method="KEYINGSET")
        if lls_actuator is not None:
            ks.paths.add(
                lls_actuator, "rotation_euler", group_method="KEYINGSET"
            )


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


class LLS_OT_InsertKeyActiveLight(bpy.types.Operator):
    bl_idname = "lls.insert_key_active_light"
    bl_label = "Insert Key for Active Light"
    bl_description = (
        "Insert a keyframe on the selected LightStudio light(s) using the "
        "LightStudio Keying Set (location.z, rotation.y, scale on the handle "
        "and rotation on the actuator)"
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

        # Temporarily activate the LightStudio keying set so the standard
        # insert operator uses its paths only, then restore the user's
        # previously active keying set.
        previous_active = scene.keying_sets.active
        scene.keying_sets.active = matches[0]
        try:
            result = bpy.ops.anim.keyframe_insert()
        finally:
            scene.keying_sets.active = previous_active

        if "CANCELLED" in result:
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
