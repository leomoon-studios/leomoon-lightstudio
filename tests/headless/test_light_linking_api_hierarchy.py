"""Headless test: native Light Linking probes and LLS hierarchy resolution.

Invoke directly::

    blender --background --factory-startup \\
        --python tests/headless/test_light_linking_api_hierarchy.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lightstudio.core import light_linking


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.stderr.flush()
    os._exit(1)


def _link(obj: bpy.types.Object) -> bpy.types.Object:
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _empty(name: str) -> bpy.types.Object:
    return _link(bpy.data.objects.new(name, None))


def _light(name: str) -> bpy.types.Object:
    data = bpy.data.lights.new(name + ".data", "AREA")
    return _link(bpy.data.objects.new(name, data))


def _mesh(name: str) -> bpy.types.Object:
    data = bpy.data.meshes.new(name + ".data")
    return _link(bpy.data.objects.new(name, data))


def main() -> None:
    if not light_linking.has_native_light_linking_api():
        _fail("Blender does not expose Object.light_linking receiver/blocker slots")
    if not light_linking.has_native_light_linking_row_state():
        _fail("Blender does not expose INCLUDE/EXCLUDE row state")

    profile = _empty("LLS_PROFILE.0")
    light_group = _empty("LLS_LIGHT.0")
    handle = _empty("LLS_LIGHT_HANDLE.0")
    basic_area = _light("LLS_LIGHT_AREA.0")
    advanced_mesh = _mesh("LLS_LIGHT_MESH.0")

    light_group.parent = profile
    handle.parent = light_group
    basic_area.parent = handle
    advanced_mesh.parent = handle

    for selected in (light_group, handle, basic_area, advanced_mesh):
        resolved = light_linking.resolve_light_handle(selected)
        if resolved != handle:
            _fail(f"{selected.name} resolved to {resolved}, expected {handle.name}")

    emitters = light_linking.resolve_light_emitters(handle)
    if emitters != (basic_area, advanced_mesh):
        _fail(f"emitters resolved to {emitters}, expected area/mesh pair")

    if not light_linking.is_valid_lightstudio_light(basic_area):
        _fail("valid Basic emitter was not accepted")
    if not light_linking.is_valid_lightstudio_light(advanced_mesh):
        _fail("valid Advanced emitter was not accepted")

    unrelated = _empty("Cube")
    if light_linking.resolve_light_handle(unrelated) is not None:
        _fail("unrelated object resolved to a LightStudio handle")
    if light_linking.is_valid_lightstudio_light(unrelated):
        _fail("unrelated object was accepted as a LightStudio light")

    malformed_handle = _empty("LLS_LIGHT_HANDLE.malformed")
    malformed_area = _light("LLS_LIGHT_AREA.malformed")
    malformed_area.parent = malformed_handle
    if light_linking.is_valid_lightstudio_light(malformed_area):
        _fail("malformed hierarchy without mesh emitter was accepted")

    ambiguous_group = _empty("LLS_LIGHT.ambiguous")
    _empty("LLS_LIGHT_HANDLE.a").parent = ambiguous_group
    _empty("LLS_LIGHT_HANDLE.b").parent = ambiguous_group
    if light_linking.resolve_light_handle(ambiguous_group) is not None:
        _fail("ambiguous light group resolved to a handle")

    print("PASS: light linking API probes and hierarchy resolution clean")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
