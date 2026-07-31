"""Headless test: Light Linking UI operators drive property sync.

Invoke directly::

    blender --background --factory-startup \\
        --python tests/headless/test_light_linking_ui.py
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
from lightstudio.operators import light_linking as light_linking_ops
from lightstudio.ui.panels import selected


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


def _build_light() -> tuple[bpy.types.Object, bpy.types.Object, bpy.types.Object]:
    light_group = _empty("LLS_LIGHT.0")
    handle = _empty("LLS_LIGHT_HANDLE.0")
    basic_area = _area("LLS_LIGHT_AREA.0")
    advanced_mesh = _mesh("LLS_LIGHT_MESH.0")
    handle.parent = light_group
    basic_area.parent = handle
    advanced_mesh.parent = handle
    bpy.context.view_layer.objects.active = basic_area
    return handle, basic_area, advanced_mesh


def _register_light_linking_ops() -> None:
    for cls in light_linking_ops.classes:
        bpy.utils.register_class(cls)


def _unregister_light_linking_ops() -> None:
    for cls in reversed(light_linking_ops.classes):
        bpy.utils.unregister_class(cls)


class _OperatorStub:
    pass


class _LayoutStub:
    def __init__(self) -> None:
        self.operators: list[str] = []
        self.props: list[str] = []
        self.labels: list[str] = []

    def separator(self) -> None:
        pass

    def column(self, align: bool = False):
        return self

    def row(self, align: bool = False):
        return self

    def split(self, factor: float = 0.0, align: bool = False):
        return self

    def box(self):
        return self

    def label(self, text: str = "", icon: str = "NONE") -> None:
        self.labels.append(text)

    def prop(self, item, property_name: str, **kwargs) -> None:
        self.props.append(property_name)

    def operator(self, operator: str, **kwargs):
        self.operators.append(operator)
        return _OperatorStub()


def main() -> None:
    properties.register()
    _register_light_linking_ops()
    handle, basic_area, advanced_mesh = _build_light()
    target = _empty("Receiver Object")
    shadow_target = _collection("Shadow Target")

    if not light_linking.is_valid_lightstudio_light(basic_area):
        _fail("Basic emitter was not accepted as a valid LightStudio light")
    if not light_linking.is_valid_lightstudio_light(advanced_mesh):
        _fail("Advanced emitter was not accepted as a valid LightStudio light")
    if light_linking.is_valid_lightstudio_light(_empty("Unrelated")):
        _fail("unrelated object was accepted as a valid LightStudio light")

    result = bpy.ops.light_studio.add_light_linking_target_row(
        category="LIGHT",
        mode="INCLUDE",
        target_type="OBJECT",
    )
    if result != {"FINISHED"}:
        _fail(f"add target row returned {result!r}")
    if len(handle.LLStudio.light_linking_include_targets) != 1:
        _fail("add target row did not add a Light Linking Include row")

    row = handle.LLStudio.light_linking_include_targets[0]
    row.object_target = target
    receiver_wrapper = basic_area.light_linking.receiver_collection
    if receiver_wrapper is None:
        _fail("dropping object into UI row did not assign receiver wrapper")
    if advanced_mesh.light_linking.receiver_collection != receiver_wrapper:
        _fail("dropping object into UI row did not sync Advanced emitter")

    result = bpy.ops.light_studio.set_light_linking_target_mode(
        category="LIGHT",
        from_mode="INCLUDE",
        mode="EXCLUDE",
        index=0,
    )
    if result != {"FINISHED"}:
        _fail(f"set mode returned {result!r}")
    if len(handle.LLStudio.light_linking_include_targets) != 0:
        _fail("set mode did not remove Include property row")
    if len(handle.LLStudio.light_linking_exclude_targets) != 1:
        _fail("set mode did not add Exclude property row")
    receiver_wrapper = basic_area.light_linking.receiver_collection
    index = receiver_wrapper.objects.find(target.name)
    if receiver_wrapper.collection_objects[index].light_linking.link_state != "EXCLUDE":
        _fail("set mode did not update native row state to EXCLUDE")

    layout = _LayoutStub()
    selected._draw_light_linking_section(layout, handle)
    for operator in (
        "light_studio.add_light_linking_target_row",
        "light_studio.set_light_linking_target_mode",
        "light_studio.clear_light_linking_row",
    ):
        if operator not in layout.operators:
            _fail(f"selected panel did not draw {operator}")
    for property_name in ("object_target",):
        if property_name not in layout.props:
            _fail(f"selected panel did not draw {property_name}")

    result = bpy.ops.light_studio.clear_light_linking_row(
        mode="EXCLUDE",
        index=0,
    )
    if result != {"FINISHED"}:
        _fail(f"clear Light Linking row returned {result!r}")
    if basic_area.light_linking.receiver_collection is not None:
        _fail("removing last UI row did not clear Basic receiver wrapper")
    if advanced_mesh.light_linking.receiver_collection is not None:
        _fail("removing last UI row did not clear Advanced receiver wrapper")

    result = bpy.ops.light_studio.add_light_linking_target_row(
        category="SHADOW",
        mode="EXCLUDE",
        target_type="COLLECTION",
    )
    if result != {"FINISHED"}:
        _fail(f"add shadow target row returned {result!r}")
    shadow_row = handle.LLStudio.shadow_linking_exclude_targets[0]
    shadow_row.collection_target = shadow_target
    if basic_area.light_linking.blocker_collection is None:
        _fail("dropping collection into Shadow Linking row did not assign blocker wrapper")
    result = bpy.ops.light_studio.clear_shadow_linking_row(
        mode="EXCLUDE",
        index=0,
    )
    if result != {"FINISHED"}:
        _fail(f"clear Shadow Linking row returned {result!r}")
    if basic_area.light_linking.blocker_collection is not None:
        _fail("clearing last Shadow Linking row did not clear Basic blocker wrapper")
    if advanced_mesh.light_linking.blocker_collection is not None:
        _fail("clearing last Shadow Linking row did not clear Advanced blocker wrapper")

    bpy.context.view_layer.objects.active = _empty("Malformed Active")
    if bpy.ops.light_studio.clear_light_linking_row.poll():
        _fail("clear Light Linking row poll should fail for malformed active object")
    if bpy.ops.light_studio.clear_shadow_linking_row.poll():
        _fail("clear Shadow Linking row poll should fail for malformed active object")

    _unregister_light_linking_ops()
    properties.unregister()
    print("PASS: light linking UI operators clean")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
