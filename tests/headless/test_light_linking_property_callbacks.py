"""Headless test: Light Linking property callbacks sync native emitters.

Invoke directly::

    blender --background --factory-startup \\
        --python tests/headless/test_light_linking_property_callbacks.py
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


def _collection(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def _state_for_object(
    collection: bpy.types.Collection,
    obj: bpy.types.Object,
) -> str | None:
    index = collection.objects.find(obj.name)
    if index < 0:
        return None
    return collection.collection_objects[index].light_linking.link_state


def _state_for_collection(
    collection: bpy.types.Collection,
    child: bpy.types.Collection,
) -> str | None:
    index = collection.children.find(child.name)
    if index < 0:
        return None
    return collection.collection_children[index].light_linking.link_state


def _build_light() -> tuple[bpy.types.Object, bpy.types.Object, bpy.types.Object]:
    light_group = _empty("LLS_LIGHT.0")
    handle = _empty("LLS_LIGHT_HANDLE.0")
    basic_area = _area("LLS_LIGHT_AREA.0")
    advanced_mesh = _mesh("LLS_LIGHT_MESH.0")
    handle.parent = light_group
    basic_area.parent = handle
    advanced_mesh.parent = handle
    return handle, basic_area, advanced_mesh


def main() -> None:
    properties.register()
    handle, basic_area, advanced_mesh = _build_light()
    receiver = _empty("Receiver Object")
    blocker_collection = _collection("Blocker Collection")

    light_row = handle.LLStudio.light_linking_include_targets.add()
    light_row.target_type = "OBJECT"
    light_row.object_target = receiver
    receiver_wrapper = basic_area.light_linking.receiver_collection
    if receiver_wrapper is None:
        _fail("object target property update did not assign receiver wrapper")
    if advanced_mesh.light_linking.receiver_collection != receiver_wrapper:
        _fail("object target property update did not sync Advanced emitter")
    if _state_for_object(receiver_wrapper, receiver) != "INCLUDE":
        _fail("object target property update did not set INCLUDE row state")

    shadow_row = handle.LLStudio.shadow_linking_exclude_targets.add()
    shadow_row.target_type = "COLLECTION"
    shadow_row.collection_target = blocker_collection
    blocker_wrapper = basic_area.light_linking.blocker_collection
    if blocker_wrapper is None:
        _fail("collection target property update did not assign blocker wrapper")
    if advanced_mesh.light_linking.blocker_collection != blocker_wrapper:
        _fail("collection target property update did not sync Advanced blocker")
    if _state_for_collection(blocker_wrapper, blocker_collection) != "EXCLUDE":
        _fail("collection target property update did not set EXCLUDE row state")

    light_linking.move_light_linking_target_row_mode(handle, "LIGHT", receiver, "EXCLUDE")
    receiver_wrapper = basic_area.light_linking.receiver_collection
    if len(handle.LLStudio.light_linking_include_targets) != 0:
        _fail("mode helper did not remove Light Linking Include property row")
    if len(handle.LLStudio.light_linking_exclude_targets) != 1:
        _fail("mode helper did not add Light Linking Exclude property row")
    if _state_for_object(receiver_wrapper, receiver) != "EXCLUDE":
        _fail("mode helper did not sync EXCLUDE row state")

    light_linking.remove_light_linking_target_row(handle, "LIGHT", "EXCLUDE", 0)
    if basic_area.light_linking.receiver_collection is not None:
        _fail("removing last Light Linking row did not clear receiver wrapper")
    if advanced_mesh.light_linking.receiver_collection is not None:
        _fail("removing last Light Linking row did not clear Advanced receiver wrapper")

    light_linking.remove_light_linking_target_row(handle, "SHADOW", "EXCLUDE", 0)
    if basic_area.light_linking.blocker_collection is not None:
        _fail("removing last Shadow Linking row did not clear blocker wrapper")
    if advanced_mesh.light_linking.blocker_collection is not None:
        _fail("removing last Shadow Linking row did not clear Advanced blocker wrapper")

    print("PASS: light linking property callbacks clean")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
