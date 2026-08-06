"""Headless regression test: equirect preview pole tiling.

Invoke directly::

    blender --background --factory-startup \\
        --python tests/headless/test_equirect_preview_offsets.py
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


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


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
    panel = gpu_layer.Panel(Vector((0, 0)), 800, 400)

    normal_verts = (
        (300, 260),
        (300, 180),
        (420, 260),
        (420, 180),
    )
    normal_offsets = gpu_layer._equirect_tile_offsets(panel, normal_verts)
    if normal_offsets != (-800, 0.0, 800):
        _fail(f"unexpected normal offsets: {normal_offsets}")
    normal_specs = gpu_layer._equirect_tile_specs(panel, normal_verts)
    if normal_specs != ((-800, "ALL"), (0.0, "ALL"), (800, "ALL")):
        _fail(f"unexpected normal specs: {normal_specs}")

    bottom_pole_verts = (
        (0, 60),
        (0, -20),
        (200, 60),
        (200, -20),
    )
    bottom_offsets = gpu_layer._equirect_tile_offsets(panel, bottom_pole_verts)
    expected_pole = (-1200, -800, -400, 0.0, 400, 800, 1200)
    if bottom_offsets != expected_pole:
        _fail(f"unexpected bottom-pole offsets: {bottom_offsets}")
    bottom_specs = gpu_layer._equirect_tile_specs(panel, bottom_pole_verts)
    expected_bottom_specs = (
        (-800, "INSIDE"),
        (0.0, "INSIDE"),
        (800, "INSIDE"),
        (-1200, "BELOW"),
        (-400, "BELOW"),
        (400, "BELOW"),
        (1200, "BELOW"),
    )
    if bottom_specs != expected_bottom_specs:
        _fail(f"unexpected bottom-pole specs: {bottom_specs}")

    top_pole_verts = (
        (0, 420),
        (0, 340),
        (200, 420),
        (200, 340),
    )
    top_offsets = gpu_layer._equirect_tile_offsets(panel, top_pole_verts)
    if top_offsets != expected_pole:
        _fail(f"unexpected top-pole offsets: {top_offsets}")
    top_specs = gpu_layer._equirect_tile_specs(panel, top_pole_verts)
    expected_top_specs = (
        (-800, "INSIDE"),
        (0.0, "INSIDE"),
        (800, "INSIDE"),
        (-1200, "ABOVE"),
        (-400, "ABOVE"),
        (400, "ABOVE"),
        (1200, "ABOVE"),
    )
    if top_specs != expected_top_specs:
        _fail(f"unexpected top-pole specs: {top_specs}")

    positions, _tex_coords, indices = gpu_layer._tessellate_inverse_equirect_light(
        panel,
        center_x=400,
        center_y=0,
        width_px=260,
        height_px=80,
        uvs=None,
        nx=80,
        ny=24,
    )
    if not indices:
        _fail("inverse pole mesh produced no triangles")
    used_x = [positions[i][0] for tri in indices for i in tri]
    if min(used_x) > panel.point_lt.x or max(used_x) < panel.point_rb.x:
        _fail(
            "inverse pole mesh did not span the full panel width: "
            f"{min(used_x)}..{max(used_x)}"
        )

    row_counts: dict[float, int] = {}
    for tri in indices:
        y = min(positions[i][1] for i in tri)
        row_counts[y] = row_counts.get(y, 0) + 1
    bottom_rows = sorted(row_counts)[:3]
    if not bottom_rows or any(row_counts[y] == 0 for y in bottom_rows):
        _fail(f"inverse pole mesh dropped bottom boundary rows: {row_counts}")

    if registered_locally:
        module.unregister()
    else:
        addon_utils.disable(EXTENSION_MODULE, default_set=False)
    print("PASS: equirect preview pole offsets clean")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
