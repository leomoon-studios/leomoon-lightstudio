"""Headless test: Light Linking sync on type switching and duplication helpers.

Invoke directly::

    blender --background --factory-startup \\
        --python tests/headless/test_light_linking_lifecycle.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lightstudio import properties
from lightstudio.core import light_linking


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.stderr.flush()
    os._exit(1)


def _link_object(obj: bpy.types.Object) -> bpy.types.Object:
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _empty(name: str) -> bpy.types.Object:
    return _link_object(bpy.data.objects.new(name, None))


def _area(name: str) -> bpy.types.Object:
    data = bpy.data.lights.new(name + ".data", "AREA")
    return _link_object(bpy.data.objects.new(name, data))


def _mesh(name: str) -> bpy.types.Object:
    data = bpy.data.meshes.new(name + ".data")
    return _link_object(bpy.data.objects.new(name, data))


def _build_light(suffix: str) -> tuple[bpy.types.Object, bpy.types.Object, bpy.types.Object]:
    light_group = _empty(f"LLS_LIGHT.{suffix}")
    handle = _empty(f"LLS_LIGHT_HANDLE.{suffix}")
    basic_area = _area(f"LLS_LIGHT_AREA.{suffix}")
    advanced_mesh = _mesh(f"LLS_LIGHT_MESH.{suffix}")
    handle.parent = light_group
    basic_area.parent = handle
    advanced_mesh.parent = handle
    return handle, basic_area, advanced_mesh


def _row_state(
    wrapper: bpy.types.Collection,
    obj: bpy.types.Object,
) -> str | None:
    index = wrapper.objects.find(obj.name)
    if index < 0:
        return None
    return wrapper.collection_objects[index].light_linking.link_state


def main() -> None:
    properties.register()
    source_handle, source_area, source_mesh = _build_light("source")
    copy_handle, copy_area, copy_mesh = _build_light("copy")
    target = _empty("Receiver Object")

    light_linking.sync_light_linking_properties(copy_handle)
    if copy_area.light_linking.receiver_collection is not None:
        _fail("empty copied light should keep receiver assignment cleared")
    if copy_mesh.light_linking.blocker_collection is not None:
        _fail("empty copied light should keep blocker assignment cleared")

    light_linking.add_light_linking_target_row(
        source_handle,
        "LIGHT",
        "INCLUDE",
        target,
    )
    receiver_wrapper = source_area.light_linking.receiver_collection
    if receiver_wrapper is None:
        _fail("source target row did not assign receiver wrapper")

    source_handle.LLStudio.type = "BASIC"
    if source_area.light_linking.receiver_collection != receiver_wrapper:
        _fail("type switch did not preserve Basic receiver wrapper")
    if source_mesh.light_linking.receiver_collection != receiver_wrapper:
        _fail("type switch did not preserve Advanced receiver wrapper")
    if _row_state(receiver_wrapper, target) != "INCLUDE":
        _fail("type switch did not preserve native INCLUDE row state")

    light_linking.copy_light_linking_properties(source_handle, copy_handle)
    copied_wrapper = copy_area.light_linking.receiver_collection
    if copied_wrapper is None:
        _fail("copy helper did not assign receiver wrapper on copied Basic emitter")
    if copy_mesh.light_linking.receiver_collection != copied_wrapper:
        _fail("copy helper did not assign receiver wrapper on copied Advanced emitter")
    if copied_wrapper == receiver_wrapper:
        _fail("copy helper reused source native receiver wrapper")
    if len(copy_handle.LLStudio.light_linking_include_targets) != 1:
        _fail("copy helper did not copy Light Linking Include property rows")
    if copy_handle.LLStudio.light_linking_include_targets[0].object_target != target:
        _fail("copy helper did not point copied row at same user target")
    if _row_state(copied_wrapper, target) != "INCLUDE":
        _fail("copy helper did not preserve native INCLUDE row state")

    print("PASS: light linking lifecycle sync clean")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
