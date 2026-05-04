"""EXR equirectangular export operator (Step 17).

Ports ``LLS_OT_render_lights_exr`` from legacy ``light_operators.py``:
swaps in a panoramic (equirectangular) Cycles camera at the LLS root,
sets EXR image-settings, fires off ``render.render``, and lets the
``render_complete`` / ``render_cancel`` handlers in
:mod:`lightstudio.handlers.app_handlers` restore everything. Original
camera + render settings + view-layer state are preserved in the
module-level ``_temp_state`` dict (mirrors legacy ``temp_props``).
"""

from __future__ import annotations

import contextlib
import os
from math import radians

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty

from ..core.scene_utils import get_lls_collection

_temp_state: dict = {}


def _restore_image_settings(image_settings, saved: dict) -> None:
    if "file_format" in saved:
        image_settings.file_format = saved["file_format"]
    for key, value in saved.items():
        with contextlib.suppress(AttributeError, TypeError, ValueError):
            setattr(image_settings, key, value)


def restore_after_render(scene: bpy.types.Scene) -> None:
    """Restore camera/render state after the EXR bake (handler entry point)."""
    if not _temp_state:
        return

    rd = scene.render
    image_settings = rd.image_settings

    rd.filepath = _temp_state.get("old_filepath", rd.filepath)

    old_camera_name = _temp_state.get("old_camera")
    if old_camera_name and old_camera_name in bpy.data.objects:
        scene.camera = bpy.data.objects[old_camera_name]

    export_camera_name = _temp_state.get("export_camera")
    camera_data_name = _temp_state.get("camera_data")
    if export_camera_name and export_camera_name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[export_camera_name])
    if camera_data_name and camera_data_name in bpy.data.cameras:
        bpy.data.cameras.remove(bpy.data.cameras[camera_data_name])

    _restore_image_settings(image_settings, _temp_state.get("image_settings", {}))
    for k, v in _temp_state.get("render", {}).items():
        with contextlib.suppress(AttributeError, TypeError, ValueError):
            setattr(rd, k, v)

    cycles = getattr(scene, "cycles", None)
    if cycles is not None and "cycles_samples" in _temp_state:
        cycles.samples = _temp_state["cycles_samples"]

    for obj_name, visible in _temp_state.get("old_camera_visibility", {}).items():
        ob = bpy.data.objects.get(obj_name)
        if ob is not None:
            ob.visible_camera = visible

    # Restore viewport shading modes that were forced off RENDERED.
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            for space in area.spaces:
                if space.type != "VIEW_3D":
                    continue
                key = f"shading::{id(space)}"
                if key in _temp_state:
                    with contextlib.suppress(AttributeError, TypeError):
                        space.shading.type = _temp_state[key]

    _temp_state.clear()


class LLS_OT_RenderLightsEXR(bpy.types.Operator):
    """Render LLS lights as an equirectangular EXR (Cycles)."""

    bl_idname = "lls.render_lights_exr"
    bl_label = "Export Lights as EXR"
    bl_description = "Renders lights as equirectangular EXR (Cycles)"
    bl_options = {"REGISTER", "UNDO"}

    samples: IntProperty(name="Max Samples", default=512)
    hdr_name: StringProperty(name="HDR File Name", default="BLS HDR")
    save_file: BoolProperty(
        name="Auto-save EXR",
        default=False,
        description="Automatically save EXR file when rendering finishes.",
    )
    width: IntProperty(name="Width", min=1, default=2160)
    height: IntProperty(name="Height", min=1, default=1080)

    @classmethod
    def poll(cls, context):
        area = getattr(context, "area", None)
        scene = getattr(context, "scene", None)
        props = getattr(scene, "LLStudio", None) if scene else None
        return bool(
            area
            and area.type == "VIEW_3D"
            and context.mode == "OBJECT"
            and props
            and props.initialized
        )

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        scene = context.scene
        rd = scene.render
        image_settings = rd.image_settings

        lls_collection = get_lls_collection(context)
        if lls_collection is None:
            self.report({"ERROR"}, "No LightStudio collection found")
            return {"CANCELLED"}

        _temp_state.clear()

        # Force every rendered-shading viewport to SOLID first, otherwise
        # switching the render engine triggers Cycles' view_update before
        # its session is initialized ('CyclesRender has no attribute session').
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type != "VIEW_3D":
                    continue
                for space in area.spaces:
                    if space.type != "VIEW_3D":
                        continue
                    if space.shading.type == "RENDERED":
                        _temp_state[f"shading::{id(space)}"] = space.shading.type
                        space.shading.type = "SOLID"

        # Capture and force camera visibility for every LLS mesh/light.
        old_visibility: dict[str, bool] = {}
        for col in lls_collection.children_recursive:
            for ob in col.objects:
                if ob.type in {"MESH", "LIGHT"}:
                    old_visibility[ob.name] = ob.visible_camera
                    ob.visible_camera = True
        _temp_state["old_camera_visibility"] = old_visibility

        # Swap in a panoramic export camera anchored at the LLS root.
        if scene.camera is None:
            self.report({"ERROR"}, "Scene has no active camera")
            _temp_state.clear()
            return {"CANCELLED"}
        _temp_state["old_camera"] = scene.camera.name

        camera_data = bpy.data.cameras.new(name="LLS HDR Export Camera")
        export_camera = bpy.data.objects.new(camera_data.name, camera_data)
        scene.collection.objects.link(export_camera)
        scene.camera = export_camera
        camera_data.type = "PANO"
        if bpy.app.version >= (4, 0, 0):
            with contextlib.suppress(AttributeError):
                camera_data.panorama_type = "EQUIRECTANGULAR"
        else:
            with contextlib.suppress(AttributeError):
                camera_data.cycles.panorama_type = "EQUIRECTANGULAR"

        root = next(
            (
                o
                for o in lls_collection.objects
                if o.name.startswith("LEOMOON_LIGHT_STUDIO")
            ),
            None,
        )
        if root is not None:
            export_camera.location = root.location
        export_camera.rotation_euler = (radians(90), radians(0), radians(-90))

        _temp_state["export_camera"] = export_camera.name
        _temp_state["camera_data"] = camera_data.name

        # Snapshot render + image settings.
        _temp_state["render"] = {
            "resolution_x": rd.resolution_x,
            "resolution_y": rd.resolution_y,
            "engine": rd.engine,
        }
        rd.engine = "CYCLES"

        _temp_state["image_settings"] = {
            p.identifier: getattr(image_settings, p.identifier)
            for p in image_settings.bl_rna.properties
            if not p.is_readonly and p.type != "POINTER"
        }
        image_settings.file_format = "OPEN_EXR"
        image_settings.color_mode = "RGBA"
        image_settings.color_depth = "32"
        with contextlib.suppress(AttributeError, TypeError):
            image_settings.exr_codec = "ZIP"

        rd.resolution_x = self.width
        rd.resolution_y = self.height

        cycles = getattr(scene, "cycles", None)
        if cycles is not None:
            _temp_state["cycles_samples"] = cycles.samples
            cycles.samples = self.samples

        # Dummy view layer with only LLS collections enabled.
        if "BLS HDR Export" in scene.view_layers:
            dummy_layer = scene.view_layers["BLS HDR Export"]
        else:
            dummy_layer = scene.view_layers.new("BLS HDR Export")
            dummy_layer.use = False

        for dummy_lc, real_lc in zip(
            dummy_layer.layer_collection.children,
            context.layer_collection.children,
            strict=False,
        ):
            if not dummy_lc.name.startswith("LLS"):
                dummy_lc.exclude = True
                continue
            _match_visibility(dummy_lc, real_lc)

        _temp_state["old_filepath"] = rd.filepath
        rd.filepath = f"{os.path.dirname(rd.filepath)}/{self.hdr_name}"

        bpy.ops.render.render(
            "INVOKE_DEFAULT",
            write_still=self.save_file,
            layer="BLS HDR Export",
        )
        return {"FINISHED"}


def _match_visibility(dummy_lc, real_lc) -> None:
    for d, r in zip(dummy_lc.children, real_lc.children, strict=False):
        d.exclude = r.exclude
        if d.exclude:
            continue
        _match_visibility(d, r)


classes: tuple[type[bpy.types.Operator], ...] = (LLS_OT_RenderLightsEXR,)
