"""Pure tests for ``lightstudio.core.material_inspect``.

Loaded by file path so ``bpy`` is never imported (matches the
textcounter pattern used by the other pure tests).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOD_PATH = ROOT / "lightstudio" / "core" / "material_inspect.py"

spec = importlib.util.spec_from_file_location("_material_inspect_under_test", MOD_PATH)
assert spec is not None and spec.loader is not None
mi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mi)


def test_empty_inputs_returns_no_groups():
    assert mi.group_inputs_by_color([]) == []


def test_no_rgba_yields_single_group():
    inputs = [("A", "VALUE", 0.0), ("B", "VALUE", 1.0)]
    assert mi.group_inputs_by_color(inputs) == [inputs]


def test_rgba_starts_new_group():
    inputs = [
        ("Texture Switch", "VALUE", 1.0),
        ("Color Overlay", "RGBA", (1.0, 1.0, 1.0, 1.0)),
        ("Color Saturation", "VALUE", 1.0),
        ("Intensity", "VALUE", 1.0),
        ("Mask Color", "RGBA", (0.0, 0.0, 0.0, 1.0)),
        ("Mask Amount", "VALUE", 0.5),
    ]
    groups = mi.group_inputs_by_color(inputs)
    assert len(groups) == 3
    assert groups[0] == [inputs[0]]
    assert groups[1] == inputs[1:4]
    assert groups[2] == inputs[4:]


def test_leading_rgba_does_not_emit_empty_group():
    inputs = [("Color", "RGBA", (1, 1, 1, 1)), ("Mix", "VALUE", 0.5)]
    groups = mi.group_inputs_by_color(inputs)
    assert groups == [inputs]
