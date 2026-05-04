"""3D Light Brush operators (Step 16).

Ports legacy ``light_brush.py``:

* ``LLSLightBrush`` — modal "click on object to position light" tool.
* ``OT_LLSFast3DEdit`` — F-key tap-to-edit; supports multi-window
  raycasts by overriding region/region_data per event.
* ``OT_LLS3DAddLight`` — Ctrl+F variant that creates a new light at the
  hit point.

Public surface:

* ``classes`` — operator tuple consumed by ``operators/__init__.py``.
* The keymap entries (F, Ctrl+F) are registered centrally by
  :mod:`lightstudio.handlers.keymaps`.
"""

from __future__ import annotations

from math import atan2, copysign

import bpy
from bpy.props import BoolProperty
from bpy_extras import view3d_utils
from mathutils import Vector
from mathutils.geometry import intersect_line_sphere

from ..core.scene_utils import find_light_grp, is_family


def _get_user_keymap_item(keymap_name: str, idname: str):
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.user
    km = kc.keymaps.get(keymap_name)
    if km is None:
        return None, None
    return km, km.keymap_items.get(idname)


def _visible_meshes(context):
    for obj in context.visible_objects:
        if is_family(obj):
            continue
        if obj.type == "MESH":
            yield (obj, obj.matrix_world.copy())
        if obj.instance_type != "NONE":
            depsgraph = getattr(context, "depsgraph", None) or context.evaluated_depsgraph_get()
            for dup in depsgraph.object_instances:
                obj_dupli = dup.object
                if obj_dupli.type == "MESH":
                    yield (obj_dupli, dup.matrix_world.copy())


def _raycast_hit(context, event):
    """Return ``(location_world, normal_world, view_vector)`` or None."""
    region = context.region
    rv3d = context.region_data
    coord = event.mouse_region_x, event.mouse_region_y

    view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    ray_target = ray_origin + view_vector

    best_length_squared = -1.0
    best_obj = None
    best_normal = None
    best_location = None

    for obj, matrix in _visible_meshes(context):
        matrix_inv = matrix.inverted()
        ray_origin_obj = matrix_inv @ ray_origin
        ray_target_obj = matrix_inv @ ray_target
        ray_direction_obj = ray_target_obj - ray_origin_obj
        success, location, normal, _face = obj.ray_cast(ray_origin_obj, ray_direction_obj)
        if not success:
            continue
        hit_world = matrix @ location
        length_squared = (hit_world - ray_origin).length_squared
        if best_obj is None or length_squared < best_length_squared:
            best_length_squared = length_squared
            best_obj = obj
            best_normal = normal
            best_location = hit_world

    if best_obj is None:
        return None

    matrix_new = best_obj.matrix_world.to_3x3().inverted().transposed()
    world_normal = matrix_new @ best_normal
    world_normal.normalize()
    return best_location, world_normal, view_vector


def _aim_active_light(context, hit_location, hit_normal, view_vector, normal_type):
    """Aim the active light's actuator at the hit point."""
    light_grp = find_light_grp(context.active_object)
    if light_grp is None or light_grp.parent is None:
        return False
    profile = light_grp.parent
    handle = next(
        (ob for ob in profile.children if ob.name.startswith("LLS_HANDLE")),
        None,
    )
    if handle is None:
        return False
    light_handle = context.active_object.parent
    actuator = light_handle.parent

    direction = hit_normal if normal_type else view_vector.reflect(hit_normal)
    position = intersect_line_sphere(
        hit_location - handle.location,
        direction + hit_location - handle.location,
        Vector((0, 0, 0)),
        light_handle.location.z,
        False,
    )[0]
    if not position:
        return False

    x, y, z = position
    actuator.rotation_euler.x = atan2(x, -y) - handle.rotation_euler.z
    actuator.rotation_euler.y = copysign(
        Vector.angle(Vector((x, y, z)), Vector((x, y, 0))), z
    )
    return True


def raycast(context, event, normal_type) -> set[str]:
    hit = _raycast_hit(context, event)
    if hit is None:
        return {"RUNNING_MODAL"}
    location, normal, view_vector = hit
    _aim_active_light(context, location, normal, view_vector, normal_type)
    return {"RUNNING_MODAL"}


def raycast_add_light(context, event, normal_type, add_light=False) -> bool:
    hit = _raycast_hit(context, event)
    if hit is None:
        return False
    location, normal, view_vector = hit
    if add_light:
        bpy.ops.scene.add_leomoon_studio_light()
    return _aim_active_light(context, location, normal, view_vector, normal_type)


class _ActiveLightPoll:
    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return (
            context.area is not None
            and context.area.type == "VIEW_3D"
            and context.mode == "OBJECT"
            and context.space_data is not None
            and context.space_data.type == "VIEW_3D"
            and context.scene.LLStudio.initialized
            and ob is not None
            and ob.name.startswith("LLS_LIGHT_")
        )


class _OverrideContext:
    pass


class _OverrideEvent:
    pass


def _build_region_override(context, event):
    """Return (override_context, override_event) for the region under the cursor."""
    screens = [w.screen for w in context.window_manager.windows]
    regions3d = [
        (area.spaces[0].region_3d, region)
        for screen in screens
        for area in screen.areas
        if area.type == context.area.type
        for region in area.regions
        if region.type == context.region.type
    ]
    active_region = context.region
    active_region_data = context.region_data
    for region_data, region in regions3d:
        if (
            event.mouse_x >= region.x
            and event.mouse_x <= region.x + region.width
            and event.mouse_y >= region.y
            and event.mouse_y <= region.y + region.height
        ):
            active_region = region
            active_region_data = region_data
            break

    override_context = _OverrideContext()
    override_context.region = active_region
    override_context.region_data = active_region_data
    override_context.visible_objects = context.visible_objects
    override_context.active_object = context.active_object
    override_context.depsgraph = (
        context.depsgraph
        if hasattr(context, "depsgraph")
        else context.evaluated_depsgraph_get()
    )
    override_event = _OverrideEvent()
    override_event.mouse_region_x = event.mouse_x - active_region.x
    override_event.mouse_region_y = event.mouse_y - active_region.y
    return override_context, override_event


# ---------------------------------------------------------------------------
# LLSLightBrush — explicit modal tool
# ---------------------------------------------------------------------------


class LLSLightBrush(bpy.types.Operator, _ActiveLightPoll):
    """Click on object to position light and reflection."""

    bl_idname = "lls.light_brush"
    bl_label = "Light Brush"
    bl_options = {"UNDO"}

    aux: BoolProperty(default=False)  # type: ignore[valid-type]
    normal_type: BoolProperty(default=False)  # type: ignore[valid-type]

    def modal(self, context, event):
        if self.aux:
            if event.type in {"LEFTMOUSE", "RIGHTMOUSE", "ESC", "RET", "NUMPAD_ENTER"}:
                self.aux = False
            return {"RUNNING_MODAL"}

        context.area.header_text_set(
            text=(
                "[LM] Select Face,  [ESC/RM] Quit,  [N] "
                + ("Reflection | <Normal>" if self.normal_type else "<Reflection> | Normal")
            )
        )

        if event.type in {
            "MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE",
            "Z", "LEFT_SHIFT", "LEFT_ALT", "LEFT_CTRL",
        }:
            return {"PASS_THROUGH"}
        if event.type in {"RIGHTMOUSE", "ESC", "RET", "NUMPAD_ENTER"}:
            context.area.header_text_set(text=None)
            return {"FINISHED"}
        if event.type == "LEFTMOUSE":
            if event.value == "PRESS":
                raycast(context, event, self.normal_type)
                return {"RUNNING_MODAL"}
            if event.value == "RELEASE":
                return {"PASS_THROUGH"}
        if event.type == "MOUSEMOVE" and event.value == "PRESS":
            raycast(context, event, self.normal_type)
            return {"PASS_THROUGH"}
        if event.type == "N" and event.value == "PRESS":
            self.normal_type = not self.normal_type

        return {"RUNNING_MODAL"}

    def invoke(self, context, event):
        if context.space_data.type != "VIEW_3D":
            self.report({"WARNING"}, "Active space must be a View3d")
            return {"CANCELLED"}
        self.beginning_tool = context.workspace.tools.from_space_view3d_mode(
            "OBJECT", create=False
        ).idname
        bpy.ops.wm.tool_set_by_id("INVOKE_DEFAULT", name="builtin.select_box")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}


# ---------------------------------------------------------------------------
# OT_LLSFast3DEdit — F-key tap-to-edit
# ---------------------------------------------------------------------------


_KEY_RELEASED = False


class OT_LLSFast3DEdit(bpy.types.Operator, _ActiveLightPoll):
    """Point on object to position light and reflection."""

    bl_idname = "light_studio.fast_3d_edit"
    bl_label = "Fast 3D Edit"
    bl_options = {"UNDO"}

    continuous: BoolProperty(  # type: ignore[valid-type]
        default=False,
        name="Hold to use",
        description=(
            "Button behaviour.\n"
            " ON: Hold button to use. Release button to stop.\n"
            " OFF: Hold LMB to use, release LMB to stop."
        ),
    )
    normal_type: BoolProperty(  # type: ignore[valid-type]
        default=False,
        name="Light along normal",
        description=(
            "Default reflection type.\n"
            " ON: Light along normal\n"
            " OFF: surface reflection (what you are looking for in most cases)"
        ),
    )

    def _restore_tool(self, context):
        context.area.header_text_set(text=None)
        with __import__("contextlib").suppress(RuntimeError, AttributeError):
            bpy.ops.wm.tool_set_by_id("INVOKE_DEFAULT", name=self.beginning_tool)

    def modal(self, context, event):
        global _KEY_RELEASED
        override_context, override_event = _build_region_override(context, event)

        context.area.header_text_set(
            text=(
                "[LM] Select Face,  [ESC/RM] Quit,  [N] "
                + ("Reflection | <Normal>" if self.normal_type else "<Reflection> | Normal")
            )
        )

        if self.continuous:
            if event.type in {
                "MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE",
                "LEFT_SHIFT", "LEFT_ALT", "LEFT_CTRL",
            }:
                return {"PASS_THROUGH"}
            if event.type in {"RIGHTMOUSE", "ESC", "RET", "NUMPAD_ENTER"}:
                self._restore_tool(context)
                return {"FINISHED"}
            if event.type == "N" and event.value == "PRESS":
                self.normal_type = not self.normal_type
                return {"RUNNING_MODAL"}
            if event.type == "MOUSEMOVE":
                raycast(override_context, override_event, self.normal_type)
                return {"PASS_THROUGH"}
            if event.value == "RELEASE" and event.type not in {
                "MOUSEMOVE", "INBETWEEN_MOUSEMOVE", "N",
            }:
                self._restore_tool(context)
                return {"FINISHED"}
            return {"RUNNING_MODAL"}

        # tap-mode
        if event.type in {
            "MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE",
            "LEFT_SHIFT", "LEFT_ALT", "LEFT_CTRL",
        }:
            return {"PASS_THROUGH"}
        if event.type in {"RIGHTMOUSE", "ESC", "RET", "NUMPAD_ENTER"}:
            self._restore_tool(context)
            return {"FINISHED"}
        if (
            event.type in {self.keymap_key, "LEFTMOUSE"}
            and event.value == "RELEASE"
            and not _KEY_RELEASED
        ):
            _KEY_RELEASED = True
            return {"RUNNING_MODAL"}
        if not _KEY_RELEASED:
            return {"RUNNING_MODAL"}
        if event.type == "N" and event.value == "PRESS":
            self.normal_type = not self.normal_type
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            raycast(override_context, override_event, self.normal_type)
            return {"PASS_THROUGH"}
        if (
            event.type == "MOUSEMOVE"
            and event.type_prev == "LEFTMOUSE"
            and event.value_prev == "PRESS"
        ):
            raycast(override_context, override_event, self.normal_type)
            return {"PASS_THROUGH"}
        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            self._restore_tool(context)
            return {"FINISHED"}
        return {"RUNNING_MODAL"}

    def invoke(self, context, event):
        global _KEY_RELEASED
        context.window_manager.modal_handler_add(self)
        self.beginning_tool = context.workspace.tools.from_space_view3d_mode(
            "OBJECT", create=False
        ).idname
        bpy.ops.wm.tool_set_by_id("INVOKE_DEFAULT", name="builtin.select_box")

        _km, kmi = _get_user_keymap_item("Object Mode", self.__class__.bl_idname)
        self.keymap_key = kmi.type if kmi else "F"
        _KEY_RELEASED = False
        if self.continuous:
            raycast(context, event, self.normal_type)
        return {"RUNNING_MODAL"}


# ---------------------------------------------------------------------------
# OT_LLS3DAddLight — Ctrl+F variant
# ---------------------------------------------------------------------------


class OT_LLS3DAddLight(bpy.types.Operator, _ActiveLightPoll):
    """Point and add light."""

    bl_idname = "light_studio.add_light_3d"
    bl_label = "Add Light in 3D"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.area is not None
            and context.area.type == "VIEW_3D"
            and context.mode == "OBJECT"
            and context.space_data is not None
            and context.space_data.type == "VIEW_3D"
            and context.scene.LLStudio.initialized
        )

    continuous: BoolProperty(default=False, name="Hold to use")  # type: ignore[valid-type]
    normal_type: BoolProperty(default=False, name="Light along normal")  # type: ignore[valid-type]

    def _restore_tool(self, context):
        context.area.header_text_set(text=None)
        with __import__("contextlib").suppress(RuntimeError, AttributeError):
            bpy.ops.wm.tool_set_by_id("INVOKE_DEFAULT", name=self.beginning_tool)

    def modal(self, context, event):
        global _KEY_RELEASED
        override_context, override_event = _build_region_override(context, event)

        context.area.header_text_set(
            text=(
                "[LM] Select Face,  [ESC/RM] Quit,  [N] "
                + ("Reflection | <Normal>" if self.normal_type else "<Reflection> | Normal")
            )
        )

        if self.continuous:
            if event.type in {
                "MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE",
                "LEFT_SHIFT", "LEFT_ALT", "LEFT_CTRL",
            }:
                return {"PASS_THROUGH"}
            if event.type in {"RIGHTMOUSE", "ESC", "RET", "NUMPAD_ENTER"}:
                self._restore_tool(context)
                return {"FINISHED"}
            if event.type == "N" and event.value == "PRESS":
                self.normal_type = not self.normal_type
                return {"RUNNING_MODAL"}
            if event.type == "MOUSEMOVE":
                self.is_added = raycast_add_light(
                    override_context, override_event, self.normal_type, not self.is_added
                )
                return {"PASS_THROUGH"}
            if event.value == "RELEASE" and event.type not in {
                "MOUSEMOVE", "INBETWEEN_MOUSEMOVE", "N",
            }:
                self._restore_tool(context)
                return {"FINISHED"}
            return {"RUNNING_MODAL"}

        if event.type in {
            "MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE",
            "LEFT_SHIFT", "LEFT_ALT", "LEFT_CTRL",
        }:
            return {"PASS_THROUGH"}
        if event.type in {"RIGHTMOUSE", "ESC", "RET", "NUMPAD_ENTER"}:
            self._restore_tool(context)
            return {"FINISHED"}
        if (
            event.type in {self.keymap_key, "LEFTMOUSE"}
            and event.value == "RELEASE"
            and not _KEY_RELEASED
        ):
            _KEY_RELEASED = True
            return {"RUNNING_MODAL"}
        if not _KEY_RELEASED:
            return {"RUNNING_MODAL"}
        if event.type == "N" and event.value == "PRESS":
            self.normal_type = not self.normal_type
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            self.is_added = raycast_add_light(
                override_context, override_event, self.normal_type, not self.is_added
            )
            return {"PASS_THROUGH"}
        if (
            event.type == "MOUSEMOVE"
            and event.type_prev == "LEFTMOUSE"
            and event.value_prev == "PRESS"
        ):
            self.is_added = raycast_add_light(
                override_context, override_event, self.normal_type, not self.is_added
            )
            return {"PASS_THROUGH"}
        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            self._restore_tool(context)
            return {"FINISHED"}
        return {"RUNNING_MODAL"}

    def invoke(self, context, event):
        global _KEY_RELEASED
        context.window_manager.modal_handler_add(self)
        self.beginning_tool = context.workspace.tools.from_space_view3d_mode(
            "OBJECT", create=False
        ).idname
        bpy.ops.wm.tool_set_by_id("INVOKE_DEFAULT", name="builtin.select_box")
        _km, kmi = _get_user_keymap_item("Object Mode", self.__class__.bl_idname)
        self.keymap_key = kmi.type if kmi else "F"
        _KEY_RELEASED = False
        self.is_added = False
        return {"RUNNING_MODAL"}


classes: tuple[type[bpy.types.Operator], ...] = (
    LLSLightBrush,
    OT_LLSFast3DEdit,
    OT_LLS3DAddLight,
)
