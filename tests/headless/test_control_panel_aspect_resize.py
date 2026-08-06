"""Headless regression test: control panel keeps calibrated preview aspect.

Invoke directly::

    blender --background --factory-startup \\
        --python tests/headless/test_control_panel_aspect_resize.py
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import addon_utils
from mathutils import Vector

EXTENSION_MODULE = "bl_ext.user_default.leomoon_lightstudio"
ROOT = Path(__file__).resolve().parents[2]
ASPECT = 16 / 9


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.stderr.flush()
    os._exit(1)


def _assert_aspect(panel, label: str) -> None:
    aspect = panel.width / panel.height
    if abs(aspect - ASPECT) > 1e-6:
        _fail(f"{label} aspect = {aspect}, expected {ASPECT}")


def main() -> None:
    registered_locally = False
    addon_utils.disable(EXTENSION_MODULE, default_set=False)
    module = addon_utils.enable(EXTENSION_MODULE, default_set=False)
    if module is None:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        module = importlib.import_module("lightstudio")
        module.register()
        registered_locally = True

    gpu_layer = importlib.import_module(f"{module.__name__}.operators.modal.gpu_layer")
    control_panel = importlib.import_module(
        f"{module.__name__}.operators.modal.control_panel"
    )
    widgets = importlib.import_module(f"{module.__name__}.core.widgets")

    panel = gpu_layer.Panel(Vector((100, 100)), 800, 450)
    control_panel._resize_panel_aspect_locked(panel, widgets.W_RIGHT, 1300, 260)
    _assert_aspect(panel, "right edge resize")
    if panel.point_lt.x != 100:
        _fail(f"right edge resize moved left anchor to {panel.point_lt.x}")

    panel = gpu_layer.Panel(Vector((100, 100)), 800, 450)
    gpu_layer.LightImage.default_size = 50
    control_panel._resize_panel_aspect_locked_and_lights(
        panel,
        widgets.W_RIGHT,
        1300,
        260,
    )
    _assert_aspect(panel, "right edge resize with lights")
    if abs(gpu_layer.LightImage.default_size - 75) > 1e-6:
        _fail(
            "preview light size did not scale with panel: "
            f"{gpu_layer.LightImage.default_size}"
        )

    panel = gpu_layer.Panel(Vector((100, 100)), 800, 450)
    control_panel._resize_panel_aspect_locked(panel, widgets.W_BOTTOM, 500, -350)
    _assert_aspect(panel, "bottom edge resize")
    if panel.point_lt.y != 550:
        _fail(f"bottom edge resize moved top anchor to {panel.point_lt.y}")

    panel = gpu_layer.Panel(Vector((100, 100)), 800, 450)
    control_panel._resize_panel_aspect_locked(
        panel,
        widgets.W_LEFT | widgets.W_TOP,
        -60,
        720,
    )
    _assert_aspect(panel, "corner resize")
    if panel.point_rb.x != 900 or panel.point_rb.y != 100:
        _fail(
            "corner resize moved opposite anchor: "
            f"rb=({panel.point_rb.x}, {panel.point_rb.y})"
        )

    if registered_locally:
        module.unregister()
    else:
        addon_utils.disable(EXTENSION_MODULE, default_set=False)
    print("PASS: control panel calibrated aspect resize clean")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
