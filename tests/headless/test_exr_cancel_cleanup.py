"""Headless regression test: EXR cancel cleanup is deferred and idempotent.

Invoke directly::

    blender --background --factory-startup \\
        --python tests/headless/test_exr_cancel_cleanup.py
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.stderr.flush()
    os._exit(1)


def main() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    exr_export = importlib.import_module("lightstudio.operators.exr_export")

    scene = bpy.context.scene
    rd = scene.render
    image_settings = rd.image_settings

    old_camera_data = bpy.data.cameras.new("LLS Test Old Camera Data")
    old_camera = bpy.data.objects.new("LLS Test Old Camera", old_camera_data)
    scene.collection.objects.link(old_camera)
    scene.camera = old_camera

    export_camera_data = bpy.data.cameras.new("LLS Test Export Camera Data")
    export_camera = bpy.data.objects.new("LLS Test Export Camera", export_camera_data)
    scene.collection.objects.link(export_camera)
    scene.camera = export_camera
    export_camera_name = export_camera.name
    export_camera_data_name = export_camera_data.name

    rd.filepath = "/tmp/lls-current"
    rd.resolution_x = 512
    rd.resolution_y = 256
    image_settings.file_format = "PNG"

    deferred: list[tuple[str | None, str | None]] = []
    original_defer = exr_export._defer_temp_datablock_removal
    exr_export._defer_temp_datablock_removal = (
        lambda obj_name, data_name: deferred.append((obj_name, data_name))
    )
    try:
        exr_export._temp_state.clear()
        exr_export._temp_state.update({
            "old_filepath": "/tmp/lls-old",
            "old_camera": old_camera.name,
            "export_camera": export_camera.name,
            "camera_data": export_camera_data.name,
            "render": {
                "resolution_x": 128,
                "resolution_y": 64,
            },
            "image_settings": {
                "file_format": "OPEN_EXR",
            },
        })

        exr_export.restore_after_render(scene)
        if exr_export._temp_state:
            _fail("restore_after_render did not clear _temp_state")
        if scene.camera != old_camera:
            _fail("restore_after_render did not restore the original camera")
        if rd.filepath != "/tmp/lls-old":
            _fail(f"render filepath was not restored: {rd.filepath}")
        if rd.resolution_x != 128 or rd.resolution_y != 64:
            _fail(f"render resolution was not restored: {rd.resolution_x}x{rd.resolution_y}")
        if not deferred:
            _fail("temporary datablock removal was not deferred")

        exr_export.restore_after_render(scene)
    finally:
        exr_export._defer_temp_datablock_removal = original_defer

    exr_export._remove_temp_datablocks(*deferred[0])
    if export_camera_name in bpy.data.objects:
        _fail("temporary export camera was not removed")
    if export_camera_data_name in bpy.data.cameras:
        _fail("temporary export camera data was not removed")

    bpy.data.objects.remove(old_camera, do_unlink=True)
    bpy.data.cameras.remove(old_camera_data)

    print("PASS: EXR cancel cleanup is deferred and idempotent")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
