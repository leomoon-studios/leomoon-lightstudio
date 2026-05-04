"""App handlers (Step 17).

Ports two persistent handlers from legacy ``light_operators.py``:

* ``_lls_update_frame`` (``frame_change_post``) syncs LLS area-light
  energy from the per-light ``intensity`` / ``color`` / ``color_saturation``
  custom properties so animated parameters update on frame change.
* ``_render_complete`` / ``_render_cancel`` restore camera + render
  settings after the EXR export bake (see
  :mod:`lightstudio.operators.exr_export`).
"""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent
from mathutils import Vector


@persistent
def _lls_update_frame(scene: bpy.types.Scene, _depsgraph=None) -> None:
    props = getattr(scene, "LLStudio", None)
    if props is None or not props.initialized:
        return
    for lls_area in (
        obj for obj in scene.objects if obj.name.startswith("LLS_LIGHT_AREA.")
    ):
        data = lls_area.data
        light_props = getattr(data, "LLStudio", None)
        if light_props is None:
            continue
        color = Vector(light_props.color)
        color_saturation = light_props.color_saturation
        intensity = light_props.intensity
        data.color = Vector((1.0, 1.0, 1.0)).lerp(color, color_saturation)
        try:
            parent = lls_area.parent
            data.energy = intensity * parent.scale.x * parent.scale.z * 250
        except (AttributeError, TypeError):
            data.energy = intensity


@persistent
def _render_complete(scene: bpy.types.Scene) -> None:
    from ..operators.exr_export import restore_after_render

    restore_after_render(scene)


@persistent
def _render_cancel(scene: bpy.types.Scene) -> None:
    from ..operators.exr_export import restore_after_render

    restore_after_render(scene)


def register() -> None:
    if _lls_update_frame not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(_lls_update_frame)
    if _render_complete not in bpy.app.handlers.render_complete:
        bpy.app.handlers.render_complete.append(_render_complete)
    if _render_cancel not in bpy.app.handlers.render_cancel:
        bpy.app.handlers.render_cancel.append(_render_cancel)


def unregister() -> None:
    if _lls_update_frame in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(_lls_update_frame)
    if _render_complete in bpy.app.handlers.render_complete:
        bpy.app.handlers.render_complete.remove(_render_complete)
    if _render_cancel in bpy.app.handlers.render_cancel:
        bpy.app.handlers.render_cancel.remove(_render_cancel)
