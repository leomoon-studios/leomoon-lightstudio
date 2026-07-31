"""Headless test: Light Linking internal buckets and native assignments.

Invoke directly::

    blender --background --factory-startup \\
        --python tests/headless/test_light_linking_native_assignment.py
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
    handle, basic_area, advanced_mesh = _build_light()
    receiver = _empty("Receiver Object")
    product_collection = _collection("Product Receivers")
    shadow_collection = _collection("Shadow Excludes")

    light_linking.sync_native_light_linking(handle)
    if basic_area.light_linking.receiver_collection is not None:
        _fail("empty Light Linking buckets should not assign receiver wrapper")
    if advanced_mesh.light_linking.blocker_collection is not None:
        _fail("empty Shadow Linking buckets should not assign blocker wrapper")

    light_linking.set_light_linking_target_mode(handle, receiver, "INCLUDE")
    light_linking.set_light_linking_target_mode(handle, product_collection, "EXCLUDE")
    light_linking.set_shadow_linking_target_mode(handle, shadow_collection, "EXCLUDE")
    light_linking.set_shadow_linking_target_mode(handle, None, "INCLUDE")
    light_linking.sync_native_light_linking(handle)

    collections = light_linking.ensure_internal_collections(handle)
    receiver_wrapper = collections[light_linking.RECEIVER_WRAPPER]
    blocker_wrapper = collections[light_linking.BLOCKER_WRAPPER]

    if basic_area.light_linking.receiver_collection != receiver_wrapper:
        _fail("Basic emitter receiver wrapper was not assigned")
    if advanced_mesh.light_linking.receiver_collection != receiver_wrapper:
        _fail("Advanced emitter receiver wrapper was not assigned")
    if basic_area.light_linking.blocker_collection != blocker_wrapper:
        _fail("Basic emitter blocker wrapper was not assigned")
    if advanced_mesh.light_linking.blocker_collection != blocker_wrapper:
        _fail("Advanced emitter blocker wrapper was not assigned")

    if _state_for_object(receiver_wrapper, receiver) != "INCLUDE":
        _fail("receiver object was not linked as INCLUDE")
    if _state_for_collection(receiver_wrapper, product_collection) != "EXCLUDE":
        _fail("receiver collection was not linked as EXCLUDE")
    if _state_for_collection(blocker_wrapper, shadow_collection) != "EXCLUDE":
        _fail("shadow collection was not linked as EXCLUDE")

    light_linking.set_light_linking_target_mode(handle, receiver, "EXCLUDE")
    light_linking.sync_native_light_linking(handle)
    if collections[light_linking.LIGHT_INCLUDE_BUCKET].objects.find(receiver.name) >= 0:
        _fail("mode change did not remove receiver from Light Include bucket")
    if collections[light_linking.LIGHT_EXCLUDE_BUCKET].objects.find(receiver.name) < 0:
        _fail("mode change did not add receiver to Light Exclude bucket")
    if _state_for_object(receiver_wrapper, receiver) != "EXCLUDE":
        _fail("receiver object mode change did not sync to native wrapper")

    light_linking.set_shadow_linking_target_mode(handle, shadow_collection, "INCLUDE")
    light_linking.sync_native_light_linking(handle)
    if collections[light_linking.SHADOW_EXCLUDE_BUCKET].children.find(shadow_collection.name) >= 0:
        _fail("mode change did not remove collection from Shadow Exclude bucket")
    if collections[light_linking.SHADOW_INCLUDE_BUCKET].children.find(shadow_collection.name) < 0:
        _fail("mode change did not add collection to Shadow Include bucket")
    if _state_for_collection(blocker_wrapper, shadow_collection) != "INCLUDE":
        _fail("shadow collection mode change did not sync to native wrapper")

    light_linking.clear_native_receiver_assignment(handle)
    light_linking.clear_native_shadow_assignment(handle)
    if basic_area.light_linking.receiver_collection is not None:
        _fail("Basic emitter receiver wrapper was not cleared")
    if advanced_mesh.light_linking.blocker_collection is not None:
        _fail("Advanced emitter blocker wrapper was not cleared")

    print("PASS: light linking native assignment helpers clean")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
