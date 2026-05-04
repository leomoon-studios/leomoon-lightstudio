"""Headless smoke test: studio create / background / renderer / delete.

Runs **inside Blender** (``blender --background --factory-startup --python ...``).

Asserts that ``scene.create_leomoon_light_studio`` appends the LLS
collection and flips ``LLStudio.initialized``, that the background and
renderer-switch operators work, and that
``scene.delete_leomoon_light_studio`` removes every ``LLS_*``
object/collection without leaving orphans.

Invoke directly::

    blender --background --factory-startup \\
        --python tests/headless/test_studio_lifecycle.py
"""

from __future__ import annotations

import sys

import addon_utils
import bpy

EXTENSION_MODULE = "bl_ext.user_default.leomoon_lightstudio"


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def _has_lls_collection(scene: bpy.types.Scene) -> bool:
    return any(c.name.startswith("LLS") for c in scene.collection.children)


def _lls_objects(scene: bpy.types.Scene) -> list[bpy.types.Object]:
    return [
        ob
        for ob in scene.objects
        if ob.name.startswith("LEOMOON_LIGHT_STUDIO") or ob.name.startswith("LLS_")
    ]


def _override_view3d(context: bpy.types.Context):
    """Return a context override pointing at the first VIEW_3D area, or None."""
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                return {"window": window, "screen": window.screen, "area": area}
    return None


def main() -> None:
    addon_utils.disable(EXTENSION_MODULE, default_set=False)
    if addon_utils.enable(EXTENSION_MODULE, default_set=False) is None:
        _fail(f"could not enable {EXTENSION_MODULE}")

    scene = bpy.context.scene

    # 1. Create.
    override = _override_view3d(bpy.context)
    if override is None:
        _fail("no VIEW_3D area available in --background screen")
    with bpy.context.temp_override(**override):
        result = bpy.ops.scene.create_leomoon_light_studio()
    if result != {"FINISHED"}:
        _fail(f"create returned {result!r}")
    if not scene.LLStudio.initialized:
        _fail("LLStudio.initialized is False after create")
    if not _has_lls_collection(scene):
        _fail("no LLS-prefixed collection at scene root after create")
    if not _lls_objects(scene):
        _fail("no LLS_* / LEOMOON_LIGHT_STUDIO objects after create")

    # 2. Renderer switch.
    bpy.ops.scene.switch_to_renderer(engine="BLENDER_EEVEE")
    if scene.render.engine != "BLENDER_EEVEE":
        _fail(f"engine is {scene.render.engine!r}, expected BLENDER_EEVEE")
    bpy.ops.scene.switch_to_renderer(engine="CYCLES")
    if scene.render.engine != "CYCLES":
        _fail(f"engine is {scene.render.engine!r}, expected CYCLES")

    # 3. Transparent background toggle.
    initial = scene.render.film_transparent
    bpy.ops.scene.set_light_studio_transparent_background()
    if scene.render.film_transparent == initial:
        _fail("film_transparent did not toggle")
    bpy.ops.scene.set_light_studio_transparent_background()
    if scene.render.film_transparent != initial:
        _fail("film_transparent did not toggle back")

    # 4. Dark background.
    bpy.ops.scene.set_light_studio_background()
    if scene.world is None or scene.world.name != "LightStudio":
        _fail(f"world is {scene.world!r}, expected 'LightStudio'")

    # 5. Delete.
    with bpy.context.temp_override(**override):
        result = bpy.ops.scene.delete_leomoon_light_studio()
    if result != {"FINISHED"}:
        _fail(f"delete returned {result!r}")
    if scene.LLStudio.initialized:
        _fail("LLStudio.initialized still True after delete")
    if _has_lls_collection(scene):
        _fail("LLS collection still present at scene root after delete")
    leftover = _lls_objects(scene)
    if leftover:
        _fail(f"leftover LLS objects after delete: {[ob.name for ob in leftover]}")
    orphans = [ob.name for ob in bpy.data.objects if ob.name.startswith(("LLS_", "LEOMOON_LIGHT_STUDIO"))]
    if orphans:
        _fail(f"orphan LLS datablocks in bpy.data.objects: {orphans}")

    addon_utils.disable(EXTENSION_MODULE, default_set=False)
    print("PASS: studio lifecycle create/background/renderer/delete clean")


if __name__ == "__main__":
    main()
