"""Property registration for LeoMoon LightStudio.

Registers (in this order, matching legacy add-on initialization):

1. ``Object.protected`` — flag consumed by the custom delete operator
   (step 16) to short-circuit ``object.delete`` on LLS-managed parts.
2. The Object subpackage classes (``LightListItem``,
   ``LeoMoon_Light_Studio_Object_Properties``).
3. The Light subpackage classes (``LeoMoon_Light_Studio_Light_Properties``).
4. The Scene subpackage classes (``ListItem``,
   ``LeoMoon_Light_Studio_Properties``) — registered last because
   ``LeoMoon_Light_Studio_Properties`` references the
   ``LightListItem`` PropertyGroup from the Object module.
5. The three ``Scene.LLStudio`` / ``Object.LLStudio`` / ``Light.LLStudio``
   pointer properties.

Unregistration runs the reverse and removes every pointer / property
this module installed (including the
``WindowManager.lls_tex_previews`` enum, which is registered later by
the texture preview list in step 13 — guarded with ``hasattr`` so the
unregister path stays idempotent until then).
"""

from __future__ import annotations

import bpy

from . import light, scene
from . import object as object_props


def register() -> None:
    bpy.types.Object.protected = bpy.props.BoolProperty(name="protected", default=False)

    for cls in object_props.classes:
        bpy.utils.register_class(cls)
    for cls in light.classes:
        bpy.utils.register_class(cls)
    for cls in scene.classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.LLStudio = bpy.props.PointerProperty(
        name="LeoMoon LightStudio Properties",
        type=scene.LeoMoon_Light_Studio_Properties,
    )
    bpy.types.Object.LLStudio = bpy.props.PointerProperty(
        name="LeoMoon LightStudio Object Properties",
        type=object_props.LeoMoon_Light_Studio_Object_Properties,
    )
    bpy.types.Light.LLStudio = bpy.props.PointerProperty(
        name="LeoMoon LightStudio Light Properties",
        type=light.LeoMoon_Light_Studio_Light_Properties,
    )


def unregister() -> None:
    if hasattr(bpy.types.WindowManager, "lls_tex_previews"):
        del bpy.types.WindowManager.lls_tex_previews

    for attr in ("LLStudio",):
        if hasattr(bpy.types.Light, attr):
            delattr(bpy.types.Light, attr)
        if hasattr(bpy.types.Object, attr):
            delattr(bpy.types.Object, attr)
        if hasattr(bpy.types.Scene, attr):
            delattr(bpy.types.Scene, attr)

    if hasattr(bpy.types.Object, "protected"):
        del bpy.types.Object.protected

    for cls in reversed(scene.classes):
        bpy.utils.unregister_class(cls)
    for cls in reversed(light.classes):
        bpy.utils.unregister_class(cls)
    for cls in reversed(object_props.classes):
        bpy.utils.unregister_class(cls)
