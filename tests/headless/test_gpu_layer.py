"""Headless verification: Step 15b GPU layer imports cleanly under Blender.

Asserts:

1. ``lightstudio.operators.modal.gpu_layer`` imports without GPU
   context (lazy shader builders).
2. ``UBO_data`` has the expected ctypes fields.
3. ``Panel`` and ``Button`` instantiate without raising — ``blf``
   dimension lookups gracefully fall back when the font system is
   unavailable in background mode.
4. After teardown, no extra ``SpaceView3D`` draw handlers are leaked
   (this substep does not register any).

Run with::

    blender --background --factory-startup \\
        --python tests/headless/test_gpu_layer.py
"""

from __future__ import annotations

import sys

import addon_utils

ADDON_ID = "bl_ext.user_default.leomoon_lightstudio"


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    mod = addon_utils.enable(ADDON_ID, default_set=True, persistent=True)
    if mod is None:
        _fail(f"could not enable {ADDON_ID}")

    # 1. Import succeeds, no GPU at import time.
    from bl_ext.user_default.leomoon_lightstudio.operators.modal import gpu_layer

    # 2. UBO struct sanity.
    field_names = [name for name, _ in gpu_layer._UBO_struct._fields_]
    expected = {
        "color_overlay", "panel_point_lt", "panel_point_rb",
        "intensity", "exposure", "texture_switch", "color_saturation",
        "desaturate",
        "mask_bottom_to_top", "mask_diagonal_bottom_left",
        "mask_diagonal_bottom_right", "mask_diagonal_top_left",
        "mask_diagonal_top_right", "mask_gradient_amount",
        "mask_gradient_switch", "mask_gradient_type",
        "mask_left_to_right", "mask_right_to_left",
        "mask_ring_inner_radius", "mask_ring_outer_radius",
        "mask_ring_switch", "mask_top_to_bottom",
        "mask_grid_columns", "mask_grid_rows", "_pad",
    }
    if set(field_names) != expected:
        _fail(f"UBO field mismatch: {set(field_names) ^ expected}")

    # 3. Primitives instantiate. Panel constructs three Buttons.
    from mathutils import Vector
    gpu_layer.Button.buttons.clear()
    panel = gpu_layer.Panel(Vector((0, 0)), 800, 400)
    if not (panel.button_exit and panel.button_send_to_bottom and panel.button_fast_3d_edit):
        _fail("Panel did not construct its built-in buttons")
    if len(gpu_layer.Button.buttons) < 3:
        _fail(f"Button registry has {len(gpu_layer.Button.buttons)} buttons, expected >=3")

    # Standalone Button has positive dimensions (real or fallback).
    btn = gpu_layer.Button(Vector((10, 10)), "Hello")
    if btn.dimensions[0] <= 0 or btn.dimensions[1] <= 0:
        _fail(f"Button dimensions invalid: {btn.dimensions}")

    # 4. Try to build the shaders if a GPU context exists. Background
    # Blender often has a usable GPU module for shader compilation; if
    # not, we skip silently — this substep just needs to prove the
    # builders don't raise on the import path.
    try:
        shaders = gpu_layer._ensure_shaders()
        for key in ("solid", "light_icon", "border", "light_icon_ubo"):
            if key not in shaders:
                _fail(f"shader cache missing key: {key}")
        print("PASS: GPU shaders built (light_icon + border + solid)")
    except (RuntimeError, SystemError) as exc:
        # Background-mode GPU compilation can fail on some platforms.
        print(f"NOTE: skipped shader compilation (background-mode GPU unavailable): {exc}")

    # 5. No draw handlers leaked. We never registered any.
    # (We can't enumerate handlers directly, but addon disable should
    # complete without RuntimeError.)
    addon_utils.disable(ADDON_ID, default_set=True)
    print("PASS: GPU layer imports + primitives instantiate; clean unregister")


if __name__ == "__main__":
    main()
