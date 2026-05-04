"""Light-data-block PropertyGroup for LeoMoon LightStudio.

Ported from ``LeoMoon_Light_Studio_Light_Properties`` in legacy
``light_operators.py``. Attached to ``Light.LLStudio`` and exposes the
basic-light color / saturation / intensity controls; ``intensity`` drives
the underlying Blender light's ``data.energy`` via the formula in the
legacy add-on (re-derived from the parent's scale).
"""

from __future__ import annotations

import bpy
from bpy.props import FloatProperty, FloatVectorProperty
from bpy.types import PropertyGroup
from mathutils import Vector


def _color_update(self: LeoMoon_Light_Studio_Light_Properties, context: bpy.types.Context) -> None:
    obj = bpy.context.object
    if obj is None or obj.type != "LIGHT":
        return
    obj.data.color = Vector((1.0, 1.0, 1.0)).lerp(Vector(self.color), self.color_saturation)


def _intensity_update(self: LeoMoon_Light_Studio_Light_Properties, context: bpy.types.Context) -> None:
    obj = bpy.context.object
    if obj is None or obj.type != "LIGHT":
        return
    parent = obj.parent
    try:
        if parent is not None:
            obj.data.energy = self.intensity * parent.scale.x * parent.scale.z * 250.0
        else:
            obj.data.energy = self.intensity
    except (AttributeError, TypeError):
        obj.data.energy = self.intensity


class LeoMoon_Light_Studio_Light_Properties(PropertyGroup):
    """Per-Light data-block LLS settings (basic-light shader inputs)."""

    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        default=(1.0, 1.0, 1.0),
        size=3,
        soft_min=0.0,
        soft_max=1.0,
        update=_color_update,
    )
    color_saturation: FloatProperty(
        name="Color Saturation",
        min=0.0,
        max=1.0,
        update=_color_update,
    )
    intensity: FloatProperty(
        name="Intensity",
        soft_min=0.0,
        soft_max=10000.0,
        default=2.0,
        update=_intensity_update,
    )


classes: tuple[type[PropertyGroup], ...] = (LeoMoon_Light_Studio_Light_Properties,)
