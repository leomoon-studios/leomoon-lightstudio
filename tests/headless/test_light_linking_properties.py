"""Headless test: Light Linking handle-level target bucket properties.

Invoke directly::

    blender --background --factory-startup \\
        --python tests/headless/test_light_linking_properties.py
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


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.stderr.flush()
    os._exit(1)


def _assert_empty_bucket(props: bpy.types.PropertyGroup, attr: str) -> None:
    bucket = getattr(props, attr)
    if len(bucket) != 0:
        _fail(f"{attr} should start empty, got {len(bucket)} entries")


def main() -> None:
    properties.register()

    handle = bpy.data.objects.new("LLS_LIGHT_HANDLE.test", None)
    bpy.context.scene.collection.objects.link(handle)
    props = handle.LLStudio

    bucket_names = (
        "light_linking_include_targets",
        "light_linking_exclude_targets",
        "shadow_linking_include_targets",
        "shadow_linking_exclude_targets",
    )
    for name in bucket_names:
        _assert_empty_bucket(props, name)

    object_target = bpy.data.objects.new("Receiver Object", None)
    bpy.context.scene.collection.objects.link(object_target)
    collection_target = bpy.data.collections.new("Receiver Collection")
    bpy.context.scene.collection.children.link(collection_target)

    include_row = props.light_linking_include_targets.add()
    include_row.target_type = "OBJECT"
    include_row.object_target = object_target
    if include_row.object_target != object_target:
        _fail("object target pointer did not round-trip")
    if include_row.collection_target is not None:
        _fail("new object target row should not have a collection target")

    exclude_row = props.shadow_linking_exclude_targets.add()
    exclude_row.target_type = "COLLECTION"
    exclude_row.collection_target = collection_target
    if exclude_row.collection_target != collection_target:
        _fail("collection target pointer did not round-trip")
    if exclude_row.object_target is not None:
        _fail("new collection target row should not have an object target")

    if len(props.light_linking_exclude_targets) != 0:
        _fail("unused Light Linking Exclude bucket should stay empty")
    if len(props.shadow_linking_include_targets) != 0:
        _fail("unused Shadow Linking Include bucket should stay empty")

    properties.unregister()
    print("PASS: light linking target bucket properties clean")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
