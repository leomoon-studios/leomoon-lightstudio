"""2D Control Panel modal operator + Grab/Scale/Rotate/Reset (Step 15c).

Ports legacy ``operators/modal.py`` (~820 lines) on top of the GPU
layer from step 15b (``gpu_layer.py``) and the pure widgets from step
15a (``core.widgets``).

Module-level surface (consumed by other subpackages via lazy import):

* :data:`panel_global` — the singleton :class:`Panel` (created on first
  invoke).
* :data:`running_modals` — count of live ``LLS_OT_control_panel``
  instances. Exposed because other operators use it as a "is the panel
  visible right now?" probe.
* :func:`update_light_sets` — resync the panel's ``LightImage`` set
  with the active profile collection.
* :func:`close_control_panel` — defensive teardown helper called from
  ``operators/studio.py`` before deleting the studio.
* :func:`add_shortkeys` / :func:`remove_shortkeys` — addon keymap
  registration for G / S / R in Object Mode (step 16's central keymap
  module will call into these).
"""

from __future__ import annotations

import contextlib
import time
import traceback
from math import pi

import bpy
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from mathutils.geometry import intersect_line_line_2d

from ...core.scene_utils import (
    family,
    find_light_profile_object,
    get_lls_collection,
    llscol_profilecol_profile_handle,
    update_light_list_set,
)
from ...core.widgets import (
    W_BOTTOM,
    W_LEFT,
    W_RIGHT,
    W_TOP,
    ClickManager,
    Vec2,
    clamp,
    is_in_rect,
)
from ..light import apply_isolate
from .gpu_layer import (
    Button,
    LightImage,
    Panel,
    _ensure_shaders,
    send_light_to_bottom,
    send_light_to_top,
)


def _isolate_light_image(context: bpy.types.Context, clicked: LightImage) -> None:
    """Toggle isolate for the LightImage's underlying LightListItem.

    Delegates to :func:`apply_isolate` so hidden lights are preserved
    when isolate is toggled off — same behaviour as the side-panel
    isolate icon and the ``light_studio.isolate`` operator.
    """
    handle_name = clicked._lls_handle.name
    props = context.scene.LLStudio
    target = next(
        (li for li in props.light_list if li.handle_name == handle_name),
        None,
    )
    if target is None:
        # Fallback to legacy behaviour if the list item can't be found.
        muted = sum(1 for light in LightImage.lights if light.mute)
        unmuted = len(LightImage.lights) - muted
        if unmuted == 1 and not clicked.mute:
            for light in LightImage.lights:
                light.mute = False
        else:
            for light in LightImage.lights:
                light.mute = True
            clicked.mute = False
        return
    apply_isolate(props, target)

VERBOSE = False


# ---------------------------------------------------------------------------
# Shared draw-set update flag (legacy ``operators/__init__`` UPDATED)
# ---------------------------------------------------------------------------

_UPDATED = True


def _is_updated() -> bool:
    return _UPDATED


def _update_clear() -> None:
    global _UPDATED
    _UPDATED = False


def _set_updated() -> None:
    global _UPDATED
    _UPDATED = True


# ---------------------------------------------------------------------------
# Module-level singletons used as the modal's external API
# ---------------------------------------------------------------------------

panel_global: Panel | None = None
running_modals: int = 0
GRABBING: bool = False
_scene_before_frame_change: str | None = None

# Step 15d: every ``SpaceView3D.draw_handler_add`` return value is
# tracked here so a single ``_remove_all_draw_handlers()`` flush can
# cover all exit paths (Esc / Return / X-button / cancel / file-load /
# addon disable / interpreter shutdown).
_draw_handlers: list = []


def _register_draw_handler(handler) -> None:
    """Track a draw handler returned by ``SpaceView3D.draw_handler_add``."""
    if handler is not None and handler not in _draw_handlers:
        _draw_handlers.append(handler)


def _remove_draw_handler(handler) -> None:
    """Remove a single tracked draw handler defensively."""
    if handler is None:
        return
    with contextlib.suppress(ValueError, AttributeError, ReferenceError, RuntimeError):
        bpy.types.SpaceView3D.draw_handler_remove(handler, "WINDOW")
    with contextlib.suppress(ValueError):
        _draw_handlers.remove(handler)


def _remove_all_draw_handlers() -> None:
    """Flush every tracked draw handler. Safe to call multiple times."""
    for handler in list(_draw_handlers):
        with contextlib.suppress(ValueError, AttributeError, ReferenceError, RuntimeError):
            bpy.types.SpaceView3D.draw_handler_remove(handler, "WINDOW")
    _draw_handlers.clear()


def close_control_panel() -> None:
    """Force-close the control panel (defensive teardown)."""
    global running_modals, panel_global
    running_modals = 0
    _remove_all_draw_handlers()
    panel_global = None


# ---------------------------------------------------------------------------
# LightOperator base mixin (legacy ``operators/__init__.LightOperator``)
# ---------------------------------------------------------------------------


class _LightOperator:
    """Poll mixin: only run when an LLS_LIGHT_* family object is active."""

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


# ---------------------------------------------------------------------------
# Draw callback for the panel modal
# ---------------------------------------------------------------------------


def _draw_panel(self, area) -> None:
    if area != bpy.context.area:
        return

    shaders = _ensure_shaders()
    solid = shaders["solid"]
    solid.uniform_float("color", (0, 0, 0, 0))
    batch_for_shader(solid, "POINTS", {"pos": [(0, 0)]}).draw(solid)

    self.panel.draw()
    for b in Button.buttons:
        b.draw(self.mouse_x, self.mouse_y)
    for light in LightImage.lights:
        light.draw()


def multiprofile_conditions(context) -> bool:
    props = context.scene.LLStudio
    if not (props.profile_multimode and running_modals):
        return True
    profile = find_light_profile_object(context.active_object)
    list_profile = props.profile_list[props.profile_list_index]
    return bool(
        list_profile.enabled and profile and profile.name == list_profile.empty_name
    )


# ---------------------------------------------------------------------------
# MouseWidget — modal sub-operator base for Grab/Scale/Rotate
# ---------------------------------------------------------------------------


class MouseWidget:
    """Modal mixin tracking mouse delta + axis lock + precision mode.

    Subclasses must implement ``_modal``, ``_finish``, ``_cancel``.
    """

    mouse_x: bpy.props.FloatProperty()  # type: ignore[valid-type]
    mouse_y: bpy.props.FloatProperty()  # type: ignore[valid-type]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ensure_widget_state()

    def _ensure_widget_state(self) -> None:
        """Initialize mixin state when Blender skips ``MouseWidget.__init__``."""
        if not hasattr(self, "_start_position"):
            self._start_position: Vector | None = None
        if not hasattr(self, "_end_position"):
            self._end_position = Vector((0, 0))
        if not hasattr(self, "_reference_end_position"):
            self._reference_end_position = Vector((0, 0))
        if not hasattr(self, "_base_rotation"):
            self._base_rotation = 0.0
        if not hasattr(self, "handler"):
            self.handler = None

        if not hasattr(self, "draw_guide"):
            self.draw_guide = True

        if not hasattr(self, "allow_xy_keys"):
            self.allow_xy_keys = False
        if not hasattr(self, "x_key"):
            self.x_key = False
        if not hasattr(self, "y_key"):
            self.y_key = False
        if not hasattr(self, "z_key"):
            self.z_key = False

        if not hasattr(self, "continous"):
            self.continous = False

        if not hasattr(self, "allow_precision_mode"):
            self.allow_precision_mode = False
        if not hasattr(self, "precision_mode"):
            self.precision_mode = False
        if not hasattr(self, "precision_offset"):
            self.precision_offset = Vector((0, 0))
        if not hasattr(self, "precision_factor"):
            self.precision_factor = 0.1

        if not hasattr(self, "z_start_position"):
            self.z_start_position = Vector((0, 0))
        if not hasattr(self, "z_end_position"):
            self.z_end_position = Vector((0, 0))

    def invoke(self, context, event):
        from math import atan2

        self._ensure_widget_state()

        mouse_x = event.mouse_x - context.area.x
        mouse_y = event.mouse_y - context.area.y

        self._start_position = Vector((self.mouse_x, self.mouse_y))
        self._end_position = Vector((mouse_x, mouse_y))
        self._reference_end_position = self._end_position.copy()
        vec = self._end_position - self._start_position
        self._base_rotation = atan2(vec.y, vec.x)

        self.handler = bpy.types.SpaceView3D.draw_handler_add(
            self._draw, (context, event), "WINDOW", "POST_PIXEL"
        )
        _register_draw_handler(self.handler)
        context.window_manager.modal_handler_add(self)

    def _cancel(self, context, event) -> None: ...
    def _finish(self, context, event) -> None: ...

    def modal(self, context, event):
        self._ensure_widget_state()

        if not context.area:
            self._unregister_handler()
            self._cancel(context, event)
            return {"CANCELLED"}

        if event.type in {"ESC", "RIGHTMOUSE"}:
            self._unregister_handler()
            self._cancel(context, event)
            return {"CANCELLED"}

        continous = getattr(self, "continous", False)
        if event.type == "RET" or (not continous and event.type == "LEFTMOUSE"):
            self._unregister_handler()
            self._finish(context, event)
            return {"FINISHED"}

        if continous and event.value == "RELEASE" and event.type == "LEFTMOUSE":
            self._unregister_handler()
            self._finish(context, event)
            return {"FINISHED"}

        self.mouse_x = event.mouse_x - context.area.x
        self.mouse_y = event.mouse_y - context.area.y
        self._end_position = Vector((self.mouse_x, self.mouse_y))

        if getattr(self, "allow_xy_keys", False) and event.value == "PRESS":
            if event.type == "X":
                self.x_key = not getattr(self, "x_key", False)
                self.y_key = False
                self.z_key = False
            elif event.type == "Y":
                self.y_key = not getattr(self, "y_key", False)
                self.x_key = False
                self.z_key = False
            elif event.type == "Z":
                self.z_key = not getattr(self, "z_key", False)
                self.x_key = False
                self.y_key = False

        if (
            self.allow_precision_mode
            and event.value == "PRESS"
            and event.type == "LEFT_SHIFT"
        ):
            self.precision_mode = True
            self._precision_mode_mid_stop = self._end_position.copy()
        elif (
            self.allow_precision_mode
            and event.value == "RELEASE"
            and event.type == "LEFT_SHIFT"
            and getattr(self, "precision_mode", False)
        ):
            self.precision_mode = False
            if hasattr(self, "_precision_mode_mid_stop"):
                self.precision_offset += (
                    self._end_position - self._precision_mode_mid_stop
                )

        return self._modal(context, event)

    def __del__(self):
        # Widget outlived its operator's RNA registration (extension reload).
        with contextlib.suppress(ReferenceError, AttributeError):
            self._unregister_handler()

    def _unregister_handler(self) -> None:
        _remove_draw_handler(getattr(self, "handler", None))
        self.handler = None

    def length(self) -> float:
        if self._start_position is None:
            return 0.0
        return (self._start_position - self._reference_end_position - self.delta_vector()).length

    def delta_vector(self) -> Vector:
        precision_factor = getattr(self, "precision_factor", 0.1)
        precision_factor_inv = 1 - precision_factor
        precision_offset = getattr(self, "precision_offset", Vector((0, 0)))
        precision_mode = getattr(self, "precision_mode", False)
        end_position = getattr(self, "_end_position", Vector((0, 0)))
        reference_end_position = getattr(self, "_reference_end_position", Vector((0, 0)))

        if precision_mode and hasattr(self, "_precision_mode_mid_stop"):
            mid = self._precision_mode_mid_stop
            return (
                mid
                - reference_end_position
                - precision_offset * precision_factor_inv
                + (end_position - mid) * precision_factor
            )
        return end_position - reference_end_position - precision_offset * precision_factor_inv

    def delta_length_factor(self) -> float:
        start = getattr(self, "_start_position", Vector((0, 0)))
        ref_end = getattr(self, "_reference_end_position", Vector((0, 0)))
        base_length = (start - ref_end).length
        if base_length < 0.0001:
            return 1.0
        return self.length() / base_length

    def angle(self) -> float:
        from math import atan2

        precision_offset = getattr(self, "precision_offset", Vector((0, 0)))
        precision_factor = getattr(self, "precision_factor", 0.1)
        start = getattr(self, "_start_position", Vector((0, 0)))
        ref_end = getattr(self, "_reference_end_position", Vector((0, 0)))
        base_rotation = getattr(self, "_base_rotation", 0.0)

        delta_vec = self.delta_vector()
        vec = ref_end - start + delta_vec + precision_offset * (1 - precision_factor)
        return atan2(vec.y, vec.x) - base_rotation

    def _draw(self, context, event):
        shaders = _ensure_shaders()
        solid = shaders["solid"]
        solid.uniform_float("color", (0.5, 0.5, 0.5, 0.5))
        batch_for_shader(solid, "LINES", {"pos": ((0, 0), (0, 0))}).draw(solid)

        if getattr(self, "draw_guide", True) and self._start_position is not None:
            solid.uniform_float("color", (0.5, 0.5, 0.5, 0.5))
            batch_for_shader(
                solid, "LINES", {"pos": (self._start_position[:], self._end_position[:])}
            ).draw(solid)

        if getattr(self, "allow_xy_keys", False) and self._start_position is not None:
            if getattr(self, "x_key", False):
                solid.uniform_float("color", (1, 0, 0, 0.5))
                batch_for_shader(
                    solid,
                    "LINES",
                    {"pos": ((0, self._start_position.y), (context.area.width, self._start_position.y))},
                ).draw(solid)
            elif getattr(self, "y_key", False):
                solid.uniform_float("color", (0, 1, 0, 0.5))
                batch_for_shader(
                    solid,
                    "LINES",
                    {"pos": ((self._start_position.x, 0), (self._start_position.x, context.area.height))},
                ).draw(solid)
            elif getattr(self, "z_key", False):
                solid.uniform_float("color", (0, 0, 1, 0.5))
                batch_for_shader(
                    solid,
                    "LINES",
                    {"pos": (self.z_start_position, self.z_end_position)},
                ).draw(solid)


# ---------------------------------------------------------------------------
# Grab / Scale / Rotate sub-operators
# ---------------------------------------------------------------------------


def _get_scale_adapter(light_object):
    return light_object.parent.scale.copy()


def _set_scale_adapter(light_object, new_scale):
    light_object.parent.scale = new_scale
    if light_object.type == "LIGHT":
        light_object.data.LLStudio.intensity = light_object.data.LLStudio.intensity


class LLS_OT_Rotate(bpy.types.Operator, MouseWidget, _LightOperator):
    bl_idname = "light_studio.rotate"
    bl_label = "Rotate Light"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_object_rotation = 0.0
        self.allow_precision_mode = True

    def invoke(self, context, event):
        global running_modals
        context.active_object.select_set(True)

        if running_modals and multiprofile_conditions(context):
            if LightImage.selected_object is None:
                idx = LightImage.find_idx(
                    context.active_object.parent.users_collection[0]
                )
                LightImage.selected_object = LightImage.lights[idx]
            active = LightImage.selected_object
            self.mouse_x = active.loc.x
            self.mouse_y = active.loc.y
        else:
            self.mouse_x = context.area.width / 2
            self.mouse_y = context.area.height / 2
        super().invoke(context, event)

        if running_modals and multiprofile_conditions(context):
            self.base_object_rotation = LightImage.selected_object._lls_handle.rotation_euler.y
        else:
            self.base_object_rotation = context.object.parent.rotation_euler.y

        return {"RUNNING_MODAL"}

    def _finish(self, context, event):
        bpy.context.workspace.status_text_set(None)

    def _cancel(self, context, event):
        if running_modals and multiprofile_conditions(context):
            LightImage.selected_object._lls_handle.rotation_euler.y = self.base_object_rotation
        else:
            context.object.parent.rotation_euler.y = self.base_object_rotation
        bpy.context.workspace.status_text_set(None)

    def _modal(self, context, event):
        if running_modals and multiprofile_conditions(context):
            LightImage.selected_object._lls_handle.rotation_euler.y = (
                self.base_object_rotation + self.angle()
            )
        else:
            context.object.parent.rotation_euler.y = self.base_object_rotation + self.angle()

        bpy.context.workspace.status_text_set(f"Rot: {self.angle():.3f}")

        if event.type not in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
            return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}


class LLS_OT_Scale(bpy.types.Operator, MouseWidget, _LightOperator):
    bl_idname = "light_studio.scale"
    bl_label = "Scale Light"
    bl_options = {"GRAB_CURSOR", "BLOCKING", "REGISTER", "UNDO", "INTERNAL"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pivot = Vector((self.mouse_x, self.mouse_y))
        self.base_object_scale = Vector((1, 1, 1))
        self.allow_xy_keys = True
        self.allow_precision_mode = True

    def invoke(self, context, event):
        context.active_object.select_set(True)

        if running_modals and multiprofile_conditions(context):
            if LightImage.selected_object is None:
                idx = LightImage.find_idx(
                    context.active_object.parent.users_collection[0]
                )
                LightImage.selected_object = LightImage.lights[idx]
            active = LightImage.selected_object
            self.mouse_x = active.loc.x
            self.mouse_y = active.loc.y
        else:
            self.mouse_x = context.area.width / 2
            self.mouse_y = context.area.height / 2
        super().invoke(context, event)

        if running_modals and multiprofile_conditions(context):
            self.base_object_scale = LightImage.selected_object._lls_handle.scale.copy()
        else:
            self.base_object_scale = _get_scale_adapter(context.object)
        return {"RUNNING_MODAL"}

    def _cancel(self, context, event):
        if running_modals and multiprofile_conditions(context):
            LightImage.selected_object._lls_handle.scale = self.base_object_scale
        else:
            _set_scale_adapter(context.object, self.base_object_scale)
        bpy.context.workspace.status_text_set(None)

    def _finish(self, context, event):
        bpy.context.workspace.status_text_set(None)

    def _modal(self, context, event):
        new_scale = self.base_object_scale * self.delta_length_factor()
        if getattr(self, "x_key", False):
            new_scale.y = self.base_object_scale.y
            new_scale.z = self.base_object_scale.z
        if getattr(self, "y_key", False):
            new_scale.x = self.base_object_scale.x
            new_scale.y = self.base_object_scale.y

        if running_modals and multiprofile_conditions(context):
            LightImage.selected_object._lls_handle.scale = new_scale
        else:
            _set_scale_adapter(context.object, new_scale)
        bpy.context.workspace.status_text_set(
            f"Scale X: {new_scale.x:.3f} Y: {new_scale.z:.3f}  [X/Y] Axis, [Shift] Precision mode"
        )

        if event.value == "PRESS" and event.type not in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
            return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}


class LLS_OT_Grab(bpy.types.Operator, MouseWidget, _LightOperator):
    bl_idname = "light_studio.grab"
    bl_label = "Grab Light"
    bl_options = {"UNDO", "GRAB_CURSOR", "BLOCKING", "INTERNAL"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pivot = Vector((self.mouse_x, self.mouse_y))
        self.base_object_rotation = Vector((0, 0, 0))
        self.allow_xy_keys = True
        self.continous = True
        self.draw_guide = False
        self.allow_precision_mode = True
        self.precision_factor = 0.05
        self.canvas_width = 1
        self.canvas_height = 1

    def invoke(self, context, event):
        global GRABBING
        context.active_object.select_set(True)
        _, _, _, handle = llscol_profilecol_profile_handle(context)
        self.profile_handle = handle

        if running_modals and multiprofile_conditions(context):
            if LightImage.selected_object is None:
                idx = LightImage.find_idx(
                    context.active_object.parent.users_collection[0]
                )
                LightImage.selected_object = LightImage.lights[idx]
            self.mouse_x = LightImage.selected_object.loc.x
            self.mouse_y = LightImage.selected_object.loc.y
            self.light_handle = LightImage.selected_object._lls_object.parent
            self.light_actuator = LightImage.selected_object._lls_actuator
            self.base_object_rotation = self.light_actuator.rotation_euler.copy()
            self.base_object_distance = self.light_handle.location.z
            if panel_global is not None:
                self.canvas_width = panel_global.width
                self.canvas_height = panel_global.height
        else:
            self.mouse_x = context.area.width / 2
            self.mouse_y = context.area.height / 2
            self.light_actuator = context.object.parent.parent
            self.light_handle = context.object.parent
            self.base_object_rotation = context.object.parent.parent.rotation_euler.copy()
            self.base_object_distance = self.light_handle.location.z
        super().invoke(context, event)
        GRABBING = True
        return {"RUNNING_MODAL"}

    def _cancel(self, context, event):
        global GRABBING
        self.light_actuator.rotation_euler = self.base_object_rotation
        self.light_handle.location.z = self.base_object_distance
        GRABBING = False
        bpy.context.workspace.status_text_set(None)

    def _finish(self, context, event):
        global GRABBING
        GRABBING = False
        bpy.context.workspace.status_text_set(None)

    def _modal(self, context, event):
        dv = self.delta_vector()
        if getattr(self, "x_key", False):
            dv.y = 0
        elif getattr(self, "y_key", False):
            dv.x = 0

        if running_modals and multiprofile_conditions(context):
            # The Control Panel preview mirrors EXR longitude, so dragging
            # right must decrease the stored actuator X rotation for the
            # visual light to follow the cursor.
            x_factor = -2 * pi / self.canvas_width
            y_factor = pi / self.canvas_height
        else:
            x_factor = 0.0025
            y_factor = 0.0025

        if getattr(self, "z_key", False):
            self.light_handle.location.z = max(
                self.base_object_distance + dv.x * 0.05, 0
            )
            import bpy_extras

            start_pos = (
                self.light_handle.matrix_world.to_translation()
                - self.profile_handle.location
            )
            start_pos = (
                start_pos.normalized() * context.space_data.clip_end
                + self.profile_handle.location
            )
            self.z_start_position = bpy_extras.view3d_utils.location_3d_to_region_2d(
                context.region, context.space_data.region_3d, start_pos
            )
            if self.z_start_position is None:
                self.z_start_position = bpy_extras.view3d_utils.location_3d_to_region_2d(
                    context.region,
                    context.space_data.region_3d,
                    self.light_handle.matrix_world.to_translation(),
                )
            self.z_end_position = bpy_extras.view3d_utils.location_3d_to_region_2d(
                context.region, context.space_data.region_3d, self.profile_handle.location
            )

            if self.z_start_position is None or self.z_end_position is None:
                self.z_start_position = Vector((0, 0))
                self.z_end_position = Vector((0, 0))

            if running_modals and panel_global is not None and multiprofile_conditions(context):
                v1 = panel_global.point_lt
                v2 = Vector((panel_global.point_rb.x, panel_global.point_lt.y))
                v3 = panel_global.point_rb
                v4 = Vector((panel_global.point_lt.x, panel_global.point_rb.y))
                shortest = None
                for a, b in ((v1, v2), (v2, v3), (v3, v4), (v1, v4)):
                    intersection = intersect_line_line_2d(
                        self.z_start_position, self.z_end_position, a, b
                    )
                    if intersection:
                        length = (self.z_start_position - intersection).length
                        if shortest is None or length < shortest:
                            shortest = length
                            self.z_end_position = intersection
        else:
            self.light_actuator.rotation_euler = self.base_object_rotation.copy()
            self.light_actuator.rotation_euler.x += dv.x * x_factor
            self.light_actuator.rotation_euler.y += dv.y * y_factor
            self.light_actuator.rotation_euler.y = clamp(
                -pi / 2 + 0.000001,
                self.light_actuator.rotation_euler.y,
                pi / 2 - 0.000001,
            )

        bpy.context.workspace.status_text_set(
            f"Move Dx: {dv.x * x_factor:.3f} Dy: {dv.y * y_factor:.3f}   "
            "[X/Y] Axis  [Z] Distance  [Shift] Precision Mode"
        )

        if event.value == "PRESS" and event.type not in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
            return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}


# ---------------------------------------------------------------------------
# App handlers (frame change + load_post running_modals reset)
# ---------------------------------------------------------------------------


from bpy.app.handlers import persistent  # noqa: E402


@persistent
def _load_pre_handler(_dummy):
    """Flush every leftover draw handler before a new file is loaded."""
    global running_modals, panel_global
    running_modals = 0
    _remove_all_draw_handlers()
    panel_global = None


@persistent
def _load_handler(_dummy):
    global running_modals, panel_global
    running_modals = 0
    # Belt-and-suspenders: also flush on load_post in case load_pre
    # was bypassed (e.g. recovering from an autosave path).
    _remove_all_draw_handlers()
    panel_global = None


@persistent
def _frame_change_handler(scene):
    global _scene_before_frame_change
    if running_modals and panel_global is not None and scene.name != _scene_before_frame_change:
        update_light_sets(panel_global, bpy.context, always=True)
        _scene_before_frame_change = scene.name


# ---------------------------------------------------------------------------
# Light-set sync
# ---------------------------------------------------------------------------


def update_light_sets(panel: Panel, context, always: bool = False) -> None:
    """Resync the on-screen ``LightImage`` set with the active profile."""
    from ...core.light_io import light_from_dict, salvage_data

    props = context.scene.LLStudio
    lls_collection = get_lls_collection(context)
    if lls_collection is None or not len(props.profile_list):
        return
    profile = props.profile_list[props.profile_list_index]
    empty = bpy.data.objects.get(profile.empty_name)
    if empty is None or not empty.users_collection:
        return
    profile_collection = empty.users_collection[0]

    if not profile.enabled and props.profile_multimode:
        working = {light._collection for light in LightImage.lights}
        for col in working:
            LightImage.remove(col)
            _update_clear()
        return

    if _is_updated() or always or len(profile_collection.children) != len(LightImage.lights):
        lls_lights = set(profile_collection.children)
        working = {light._collection for light in LightImage.lights}
        to_delete = working - lls_lights
        to_add = lls_lights - working

        for col in to_delete:
            LightImage.remove(col)

        for col in to_add:
            try:
                LightImage(context, panel, col)
            except Exception:  # noqa: BLE001
                # Salvage flow: rebuild the malformed light from its data dict.
                if VERBOSE:
                    traceback.print_exc()
                objects = list(col.objects)
                light_root = next(
                    (ob for ob in objects if ob.name.startswith("LLS_LIGHT.")), None
                )
                family_obs = family(light_root) if light_root else []
                light_data = salvage_data(col)
                for obj in family_obs:
                    bpy.data.objects.remove(obj)
                bpy.data.collections.remove(col)
                light_from_dict(light_data, profile_collection)

        _update_clear()


# ---------------------------------------------------------------------------
# Reset-control-panel
# ---------------------------------------------------------------------------


class LLS_OT_ResetControlPanel(bpy.types.Operator):
    bl_idname = "light_studio.reset_control_panel"
    bl_label = "Reset Control Panel"
    bl_description = "Reset Control Panel to default position and icon size"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return running_modals > 0 and panel_global is not None

    def execute(self, context):
        aw = context.area.width
        width = min(aw - 60, 800)
        height = width * (9 / 16)
        start_point = Vector((15, 45))
        panel_global.point_lt = Vec2((
            min(start_point.x, start_point.x + width),
            max(start_point.y, start_point.y + height),
        ))
        panel_global.point_rb = Vec2((
            max(start_point.x, start_point.x + width),
            min(start_point.y, start_point.y + height),
        ))
        panel_global.move(Vector([0, 0]))
        LightImage.change_default_size(50)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Main control panel modal
# ---------------------------------------------------------------------------


class LLS_OT_control_panel(bpy.types.Operator):
    bl_idname = "light_studio.control_panel"
    bl_label = "LightStudio Control Panel"
    bl_description = "Show/Hide LightStudio Control Panel"

    mouse_x: bpy.props.IntProperty()  # type: ignore[valid-type]
    mouse_y: bpy.props.IntProperty()  # type: ignore[valid-type]

    @classmethod
    def poll(cls, context):
        return (
            context.area is not None
            and context.area.type == "VIEW_3D"
            and context.mode == "OBJECT"
            and context.scene.LLStudio.initialized
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.handler = None
        self.panel = None
        self.panel_moving = False
        self.clicked_object = None
        self.click_manager = ClickManager(clock=time.time)
        self.active_feature = None
        self.precision_mode = False
        self.border_touch = 0
        self.modifier_key = False
        self.ctrl = False

    def __del__(self):
        # Widget outlived its operator's RNA registration (extension reload).
        with contextlib.suppress(ReferenceError, AttributeError):
            self._unregister_handler()

    def _unregister_handler(self):
        global running_modals
        running_modals = max(0, running_modals - 1)
        _remove_draw_handler(getattr(self, "handler", None))
        self.handler = None

    def _mouse_event(self, context, event):
        area_mouse_x = event.mouse_x - context.area.x
        area_mouse_y = event.mouse_y - context.area.y
        dx = area_mouse_x - self.mouse_x
        dy = area_mouse_y - self.mouse_y
        self.mouse_x = area_mouse_x
        self.mouse_y = area_mouse_y
        return dx, dy, area_mouse_x, area_mouse_y

    def invoke(self, context, event):
        global running_modals, panel_global
        update_light_list_set(context)

        running_modals += 1
        if running_modals > 1:
            running_modals = 0  # toggle off
            return {"CANCELLED"}

        self.handler = bpy.types.SpaceView3D.draw_handler_add(
            _draw_panel, (self, context.area), "WINDOW", "POST_PIXEL"
        )
        _register_draw_handler(self.handler)
        context.window_manager.modal_handler_add(self)
        aw = context.area.width
        pw = min(aw - 60, 800)

        if not panel_global:
            panel_global = Panel(Vector((15, 45)), pw, pw * (9 / 16))
        self.panel = panel_global
        LightImage.default_size = 50

        self.mouse_x = event.mouse_x - context.area.x
        self.mouse_y = event.mouse_y - context.area.y

        update_light_sets(self.panel, context, always=True)
        self.ctrl = False
        self.modifier_key = False
        return {"RUNNING_MODAL"}

    def _border_touch_point(self, context, area_mouse_x, area_mouse_y):
        touch_point = 0
        threshold = 5

        r_ui = next((r for r in context.area.regions if r.type == "UI"), None)
        if r_ui is not None:
            if r_ui.alignment == "RIGHT":
                if area_mouse_x >= context.area.width - r_ui.width - 2:
                    return touch_point
            elif area_mouse_x <= r_ui.width + 2:
                return touch_point

        for b in Button.buttons:
            if is_in_rect(b, Vector((area_mouse_x, area_mouse_y))):
                context.window.cursor_set("DEFAULT")
                return 0

        if (
            area_mouse_y >= self.panel.point_rb.y - threshold
            and area_mouse_y <= self.panel.point_lt.y + threshold
        ):
            if (
                area_mouse_x < self.panel.point_lt.x + threshold
                and area_mouse_x >= self.panel.point_lt.x - threshold
            ):
                touch_point |= W_LEFT
                context.window.cursor_set("MOVE_X")
            elif (
                area_mouse_x > self.panel.point_rb.x - threshold
                and area_mouse_x <= self.panel.point_rb.x + threshold
            ):
                touch_point |= W_RIGHT
                context.window.cursor_set("MOVE_X")

        if (
            area_mouse_x >= self.panel.point_lt.x - threshold
            and area_mouse_x <= self.panel.point_rb.x + threshold
        ):
            if (
                area_mouse_y > self.panel.point_lt.y - threshold
                and area_mouse_y <= self.panel.point_lt.y + threshold
            ):
                touch_point |= W_TOP
                context.window.cursor_set("MOVE_Y")
            elif (
                area_mouse_y < self.panel.point_rb.y + threshold
                and area_mouse_y >= self.panel.point_rb.y - threshold
            ):
                touch_point |= W_BOTTOM
                context.window.cursor_set("MOVE_Y")

        if touch_point in {W_LEFT | W_TOP, W_LEFT | W_BOTTOM, W_RIGHT | W_TOP, W_RIGHT | W_BOTTOM}:
            context.window.cursor_set("SCROLL_XY")
        elif touch_point == 0:
            context.window.cursor_set("DEFAULT")

        return touch_point

    def find_clicked(self, area_mouse_x, area_mouse_y, overlapping=False):
        r_ui = next(
            (r for r in bpy.context.area.regions if r.type == "UI"), None
        )
        if r_ui is not None:
            if r_ui.alignment == "RIGHT":
                if area_mouse_x >= bpy.context.area.width - r_ui.width - 2:
                    return None
            elif area_mouse_x <= r_ui.width + 2:
                return None

        overlapped = []
        for light in reversed(LightImage.lights):
            if light.is_mouse_over(area_mouse_x, area_mouse_y):
                if not overlapping:
                    return light
                overlapped.append(light)

        if overlapping and overlapped:
            return overlapped

        for b in Button.buttons:
            if is_in_rect(b, Vector((area_mouse_x, area_mouse_y))):
                return b
        if is_in_rect(self.panel, Vector((area_mouse_x, area_mouse_y))):
            return self.panel
        return None

    def modal(self, context, event):
        global running_modals
        if running_modals < 1:
            self._unregister_handler()
            if context.area:
                context.area.tag_redraw()
            return {"FINISHED"}

        if not context.area or (context.object and context.object.mode != "OBJECT"):
            self._unregister_handler()
            return {"CANCELLED"}

        try:
            context.area.tag_redraw()

            update_light_sets(self.panel, context)
            LightImage.refresh()

            if event.type in {"TIMER", "NONE", "WINDOW_DEACTIVATE"}:
                self.ctrl = False
                self.modifier_key = False
            elif event.type in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
                dx, dy, area_mouse_x, area_mouse_y = self._mouse_event(context, event)

                touch_point = self._border_touch_point(context, area_mouse_x, area_mouse_y)
                if self.border_touch and event.value_prev == "PRESS":
                    if self.border_touch & W_LEFT:
                        self.panel.point_lt.x = min(area_mouse_x, self.panel.point_rb.x - 100)
                    elif self.border_touch & W_RIGHT:
                        self.panel.point_rb.x = max(area_mouse_x, self.panel.point_lt.x + 100)
                    if self.border_touch & W_TOP:
                        self.panel.point_lt.y = max(area_mouse_y, self.panel.point_rb.y + 100)
                    elif self.border_touch & W_BOTTOM:
                        self.panel.point_rb.y = min(area_mouse_y, self.panel.point_lt.y - 100)
                    self.panel.move(Vector([0, 0]))

                if self.clicked_object and self.panel_moving:
                    if isinstance(self.clicked_object, Panel):
                        f = 0.1 if self.precision_mode else 1
                        self.clicked_object.move(Vector((dx * f, dy * f)))
                    elif isinstance(self.clicked_object, Button):
                        pass
                    else:
                        active = LightImage.selected_object
                        if active and not GRABBING:
                            bpy.ops.light_studio.grab(
                                "INVOKE_DEFAULT", mouse_x=active.loc.x, mouse_y=active.loc.y
                            )
                            self.panel_moving = False
                    return {"RUNNING_MODAL"}
                return {"PASS_THROUGH"}

            if event.value == "PRESS":
                if event.type in {
                    "LEFT_CTRL", "RIGHT_CTRL", "LEFT_SHIFT",
                    "RIGHT_SHIFT", "LEFT_ALT", "RIGHT_ALT",
                }:
                    self.modifier_key = True
                if event.type == "LEFT_CTRL":
                    self.ctrl = True

                elif event.type == "RIGHTMOUSE":
                    _, _, area_mouse_x, area_mouse_y = self._mouse_event(context, event)
                    self.clicked_object = self.find_clicked(area_mouse_x, area_mouse_y)
                    if not self.clicked_object:
                        return {"PASS_THROUGH"}

                    if hasattr(self.clicked_object, "mute"):
                        _isolate_light_image(context, self.clicked_object)

                    if hasattr(self.clicked_object, "select"):
                        self.clicked_object.select()
                    return {"RUNNING_MODAL"}

                elif event.type == "LEFTMOUSE":
                    _, _, area_mouse_x, area_mouse_y = self._mouse_event(context, event)
                    overlapped = self.find_clicked(area_mouse_x, area_mouse_y, overlapping=True)
                    if isinstance(overlapped, list):
                        self.clicked_object = overlapped[0] if overlapped else None
                    else:
                        self.clicked_object = overlapped

                    touch_point = self._border_touch_point(context, area_mouse_x, area_mouse_y)
                    if touch_point and not isinstance(self.clicked_object, Button):
                        self.border_touch = touch_point
                        return {"RUNNING_MODAL"}

                    self.panel_moving = self.clicked_object is not None
                    click_result = self.click_manager.click(self.clicked_object)

                    if not self.ctrl and hasattr(self.clicked_object, "mute"):
                        if click_result == "TRIPLE":
                            _isolate_light_image(context, self.clicked_object)
                        elif click_result == "DOUBLE":
                            self.clicked_object.mute = not self.clicked_object.mute

                    if hasattr(self.clicked_object, "select"):
                        try:
                            self.clicked_object.select()
                        except RuntimeError:
                            update_light_sets(self.panel, context, always=True)
                            if VERBOSE:
                                traceback.print_exc()
                        else:
                            if self.ctrl and isinstance(overlapped, list) and len(overlapped) > 1:
                                send_light_to_bottom(self.clicked_object)
                                next_clicked = self.find_clicked(area_mouse_x, area_mouse_y)
                                if next_clicked is not None and hasattr(next_clicked, "select"):
                                    next_clicked.select()
                            else:
                                send_light_to_top(self.clicked_object)

                    if hasattr(self.clicked_object, "click"):
                        result = self.clicked_object.click()
                        if result == "FINISHED":
                            bpy.context.workspace.status_text_set(None)
                            self._unregister_handler()
                            return {"FINISHED"}
                        return {"RUNNING_MODAL"}

                    if self.clicked_object:
                        return {"RUNNING_MODAL"}
                    return {"PASS_THROUGH"}

                elif event.type == "NUMPAD_PLUS":
                    LightImage.change_default_size(LightImage.default_size + 10)
                    return {"RUNNING_MODAL"}
                elif event.type == "NUMPAD_MINUS":
                    LightImage.change_default_size(LightImage.default_size - 10)
                    return {"RUNNING_MODAL"}
                elif event.type == "LEFT_SHIFT":
                    self.precision_mode = True
                    return {"RUNNING_MODAL"}
                elif event.type == "RET":
                    bpy.context.workspace.status_text_set(None)
                    self._unregister_handler()
                    return {"FINISHED"}

            if event.value == "RELEASE":
                if event.type in {
                    "LEFT_CTRL", "RIGHT_CTRL", "LEFT_SHIFT",
                    "RIGHT_SHIFT", "LEFT_ALT", "RIGHT_ALT",
                }:
                    self.modifier_key = False
                if event.type == "LEFTMOUSE":
                    self.panel_moving = False
                    self.border_touch = 0
                elif event.type == "LEFT_SHIFT":
                    self.precision_mode = False
                    return {"RUNNING_MODAL"}
            elif event.value == "CLICK" and event.type == "LEFTMOUSE":
                return {"PASS_THROUGH"}
        except Exception:  # noqa: BLE001
            self._unregister_handler()
            if VERBOSE:
                traceback.print_exc()
            return {"CANCELLED"}

        return {"PASS_THROUGH"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    LLS_OT_Grab,
    LLS_OT_Scale,
    LLS_OT_Rotate,
    LLS_OT_ResetControlPanel,
    LLS_OT_control_panel,
)


_addon_keymaps: list = []


def add_shortkeys() -> None:
    """Register G/S/R keymap entries for Object Mode."""
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc is None:
        return
    km = kc.keymaps.new(name="Object Mode", space_type="EMPTY")
    for op_cls, key in (
        (LLS_OT_Grab, "G"),
        (LLS_OT_Scale, "S"),
        (LLS_OT_Rotate, "R"),
    ):
        kmi = km.keymap_items.new(op_cls.bl_idname, key, "PRESS")
        _addon_keymaps.append((km, kmi))


def remove_shortkeys() -> None:
    for km, kmi in _addon_keymaps:
        with contextlib.suppress(RuntimeError, ReferenceError):
            km.keymap_items.remove(kmi)
    _addon_keymaps.clear()


def register() -> None:
    for cls in classes:
        bpy.utils.register_class(cls)
    if _load_pre_handler not in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.append(_load_pre_handler)
    if _load_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_handler)
    if _frame_change_handler not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(_frame_change_handler)
    # G/S/R keymaps are now registered by handlers/keymaps.py.


def unregister() -> None:
    # G/S/R keymaps are unregistered by handlers/keymaps.py before
    # this runs; remove_shortkeys() here is a no-op safety net.
    # G/S/R keymaps are unregistered by handlers/keymaps.py before
    # this runs; remove_shortkeys() here is a no-op safety net.
    remove_shortkeys()
    if _frame_change_handler in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(_frame_change_handler)
    if _load_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_handler)
    if _load_pre_handler in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(_load_pre_handler)
    for cls in reversed(classes):
        with contextlib.suppress(RuntimeError):
            bpy.utils.unregister_class(cls)
    # atexit-style guard: flush any leftover draw handlers + state so a
    # subsequent re-register starts from a clean slate.
    close_control_panel()
    _remove_all_draw_handlers()
