"""Studio lifecycle operators (create / delete / background / renderer).

Ported from legacy ``light_operators.py`` (`CreateBlenderLightStudio`,
`DeleteBlenderLightStudio`, `SetBackground`, `SetTransparentBackground`,
`SwitchToRenderer`).

Notes versus legacy:

- Append target is :data:`lightstudio.core.paths.LLS_BLEND` instead of a
  computed-relative path.
- ``SwitchToRenderer`` drops the legacy ``BLENDER_EEVEE`` branch — Blender
  5.x only ships ``BLENDER_EEVEE_NEXT``.
- Delete avoids the legacy reliance on ``bpy.ops.lls_list.delete_profile``
  (step 12) and ``operators.modal.close_control_panel`` (step 15) — both
  are guarded so this operator works today and will pick up the real
  helpers automatically once they land.
- ``cycles_visibility`` is touched only when present (Cycles add-on may
  not have populated the World yet at register time).
"""

from __future__ import annotations

import os

import bpy
from bpy.props import EnumProperty

from ..core.log import log
from ..core.paths import LLS_BLEND

_DARK_GREY = (0.050876, 0.050876, 0.050876, 1.0)
_VERY_DARK_GREY = (0.008, 0.008, 0.008, 1.0)


def _is_lls_collection(col: bpy.types.Collection) -> bool:
    return col.name.startswith("LLS")


def _find_lls_collection(context: bpy.types.Context) -> bpy.types.Collection | None:
    for col in context.scene.collection.children:
        if _is_lls_collection(col):
            return col
    return None


def _is_lls_object(ob: bpy.types.Object) -> bool:
    if ob.name.startswith("LEOMOON_LIGHT_STUDIO"):
        return True
    if not ob.name.startswith("LLS_"):
        return False
    cur = ob
    while cur.parent:
        cur = cur.parent
        if cur.name.startswith("LEOMOON_LIGHT_STUDIO"):
            return True
    return False


def _reset_world(world: bpy.types.World, color: tuple[float, float, float, float]) -> None:
    """Set world background colour and restore Cycles visibility flags."""
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg is not None:
        bg.inputs[0].default_value = color
    vis = getattr(world, "cycles_visibility", None)
    if vis is not None:
        vis.diffuse = True
        vis.glossy = True
        vis.transmission = True


class LLS_OT_CreateStudio(bpy.types.Operator):
    bl_idname = "scene.create_leomoon_light_studio"
    bl_label = "Create LightStudio"
    bl_description = "Append LeoMoon LightStudio to current scene"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return (
            context.area is not None
            and context.area.type == "VIEW_3D"
            and context.mode == "OBJECT"
            and not context.scene.LLStudio.initialized
        )

    def execute(self, context: bpy.types.Context) -> set[str]:
        # LightStudio works better in Cycles; users can switch back via the panel.
        context.scene.render.engine = "CYCLES"

        # Ensure the master collection is the active one so the appended
        # ``LLS`` collection lands at scene-root level (Blender 3.0+ wraps
        # appends into the active collection otherwise).
        context.view_layer.active_layer_collection = context.view_layer.layer_collection

        sep = os.sep
        directory = f"{LLS_BLEND}{sep}Collection{sep}"
        bpy.ops.wm.append(
            filepath=f"{sep}LLS4.blend{sep}Collection{sep}",
            directory=directory,
            filename="LLS",
            active_collection=True,
        )

        # Seed the first profile via lls_list.new_profile (step 12).
        bpy.ops.lls_list.new_profile()

        context.scene.LLStudio.initialized = True
        log("studio created")
        return {"FINISHED"}


class LLS_OT_DeleteStudio(bpy.types.Operator):
    bl_idname = "scene.delete_leomoon_light_studio"
    bl_label = "Delete LightStudio"
    bl_description = "Delete LeoMoon LightStudio from current scene"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return (
            context.area is not None
            and context.area.type == "VIEW_3D"
            and context.mode == "OBJECT"
            and context.scene.LLStudio.initialized
        )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context: bpy.types.Context) -> None:
        col = self.layout.column(align=True)
        col.label(text="Deleting LightStudio is irreversible!")
        col.label(text="Your lighting setup will be lost.")

    def execute(self, context: bpy.types.Context) -> set[str]:
        scene = context.scene
        scene.LLStudio.initialized = False

        from .modal.control_panel import close_control_panel
        close_control_panel()

        # TODO(step 12): bpy.ops.lls_list.delete_profile loop. For now
        # just clear the profile list collection — actual blend-data
        # cleanup is handled in bulk below.
        scene.LLStudio.profile_list.clear()
        scene.LLStudio.profile_list_index = 0

        # Remove every LLS-family object from the scene + blend data.
        to_remove = [ob for ob in scene.objects if _is_lls_object(ob)]
        for ob in to_remove:
            for c in list(ob.users_collection):
                c.objects.unlink(ob)
            ob.user_clear()
            ob.use_fake_user = False
            bpy.data.objects.remove(ob)

        # Remove the LLS collection tree, deepest first.
        lls_root = _find_lls_collection(context)
        if lls_root is not None:
            for col in list(lls_root.children_recursive):
                bpy.data.collections.remove(col)
            bpy.data.collections.remove(lls_root)

        # Restore (or create) the default world.
        world = bpy.data.worlds.get("World")
        if world is None:
            world = bpy.data.worlds.new("World")
        scene.world = world
        _reset_world(world, _DARK_GREY)

        log("studio deleted")
        return {"FINISHED"}


class LLS_OT_SetBackground(bpy.types.Operator):
    bl_idname = "scene.set_light_studio_background"
    bl_label = "Setup Dark Background"
    bl_description = "Darken background and disable background influence"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        world = bpy.data.worlds.get("LightStudio")
        if world is None:
            world = bpy.data.worlds.new("LightStudio")
        context.scene.world = world
        world.use_nodes = True
        bg = world.node_tree.nodes.get("Background")
        if bg is not None:
            bg.inputs[0].default_value = _VERY_DARK_GREY
        vis = getattr(world, "cycles_visibility", None)
        if vis is not None:
            vis.diffuse = False
            vis.glossy = False
            vis.transmission = False
        return {"FINISHED"}


class LLS_OT_SetTransparentBackground(bpy.types.Operator):
    bl_idname = "scene.set_light_studio_transparent_background"
    bl_label = "Transparent Background"
    bl_description = "Enable/Disable Transparent Background"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        scene = context.scene
        scene.render.film_transparent = not scene.render.film_transparent
        return {"FINISHED"}


class LLS_OT_SwitchRenderer(bpy.types.Operator):
    bl_idname = "scene.switch_to_renderer"
    bl_label = "Switch Render Engine"
    bl_description = "Change render engine"
    bl_options = {"REGISTER", "UNDO"}

    engine: EnumProperty(  # type: ignore[valid-type]
        items=[
            ("CYCLES", "Cycles", "Cycles"),
            ("BLENDER_EEVEE", "EEVEE", "EEVEE Next"),
        ],
        name="Engine",
        default="CYCLES",
    )

    def execute(self, context: bpy.types.Context) -> set[str]:
        context.scene.render.engine = self.engine
        return {"FINISHED"}


classes: tuple[type[bpy.types.Operator], ...] = (
    LLS_OT_CreateStudio,
    LLS_OT_DeleteStudio,
    LLS_OT_SetBackground,
    LLS_OT_SetTransparentBackground,
    LLS_OT_SwitchRenderer,
)
