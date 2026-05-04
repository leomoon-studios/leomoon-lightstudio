"""Pure tests for ``lightstudio.core.widgets``.

Loaded by file path so ``bpy`` / ``mathutils`` / ``gpu`` are never
imported (matches the textcounter pattern used by the other pure tests).
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOD_PATH = ROOT / "lightstudio" / "core" / "widgets.py"

spec = importlib.util.spec_from_file_location("_widgets_under_test", MOD_PATH)
assert spec is not None and spec.loader is not None
widgets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(widgets)

Vec2 = widgets.Vec2
Rectangle = widgets.Rectangle
ClickManager = widgets.ClickManager


# ---------------------------------------------------------------------------
# Vec2
# ---------------------------------------------------------------------------


def test_vec2_arithmetic():
    a = Vec2((1.0, 2.0))
    b = Vec2((3.0, 4.0))
    assert (a + b) == Vec2((4.0, 6.0))
    assert (b - a) == Vec2((2.0, 2.0))
    assert (a * 2) == Vec2((2.0, 4.0))
    assert (a / 2) == Vec2((0.5, 1.0))


def test_vec2_accepts_duck_typed_input():
    class V:
        x = 5.0
        y = 7.0
    v = Vec2(V())
    assert (v.x, v.y) == (5.0, 7.0)


# ---------------------------------------------------------------------------
# clamp
# ---------------------------------------------------------------------------


def test_clamp():
    assert widgets.clamp(0, -5, 10) == 0
    assert widgets.clamp(0, 5, 10) == 5
    assert widgets.clamp(0, 50, 10) == 10


# ---------------------------------------------------------------------------
# Rectangle
# ---------------------------------------------------------------------------


def test_rectangle_basic_geometry():
    # construct rect from origin with positive width/height
    r = Rectangle(Vec2((10, 20)), 100, 50)
    # width/height extend from start_point: start_point.y is the *bottom* when
    # height is positive (matches legacy Vector arithmetic)
    assert r.point_lt.x == 10
    assert r.point_rb.x == 110
    assert r.point_lt.y == 70
    assert r.point_rb.y == 20
    assert r.width == 100
    assert r.height == 50
    assert r.loc == Vec2((60, 45))


def test_rectangle_loc_setter_translates():
    r = Rectangle(Vec2((0, 0)), 100, 100)
    r.loc = Vec2((200, 200))
    assert r.point_lt == Vec2((150, 250))
    assert r.point_rb == Vec2((250, 150))


def test_rectangle_resize_around_centre():
    r = Rectangle(Vec2((0, 0)), 100, 100)
    centre = r.loc
    r.width = 200
    r.height = 60
    assert r.loc == centre
    assert r.width == 200
    assert r.height == 60


# ---------------------------------------------------------------------------
# is_in_rect
# ---------------------------------------------------------------------------


def test_is_in_rect():
    r = Rectangle(Vec2((0, 0)), 100, 100)
    assert widgets.is_in_rect(r, Vec2((50, 50)))
    assert widgets.is_in_rect(r, Vec2((0, 0)))  # corner counts as inside
    assert widgets.is_in_rect(r, Vec2((100, 100)))
    assert not widgets.is_in_rect(r, Vec2((-1, 50)))
    assert not widgets.is_in_rect(r, Vec2((50, 101)))


# ---------------------------------------------------------------------------
# border_touch_point
# ---------------------------------------------------------------------------


def test_border_touch_point_classification():
    btp = widgets.border_touch_point
    r = Rectangle(Vec2((0, 0)), 100, 100)  # lt=(0,100), rb=(100,0)

    assert btp(r, 50, 50) == 0  # interior
    assert btp(r, 0, 50) == widgets.W_LEFT
    assert btp(r, 100, 50) == widgets.W_RIGHT
    assert btp(r, 50, 100) == widgets.W_TOP
    assert btp(r, 50, 0) == widgets.W_BOTTOM
    # corners are bitwise ORs of two flags
    assert btp(r, 0, 100) == widgets.W_LEFT | widgets.W_TOP
    assert btp(r, 100, 0) == widgets.W_RIGHT | widgets.W_BOTTOM
    # well outside the threshold -> 0
    assert btp(r, -50, 50) == 0


# ---------------------------------------------------------------------------
# Rectangle rotation
# ---------------------------------------------------------------------------


def test_rectangle_get_verts_rotates_around_centre():
    r = Rectangle(Vec2((-50, -50)), 100, 100)  # centred on origin
    r.rot = math.pi / 2  # 90°
    verts = r.get_verts()
    # original lt = (-50, 50); rotated by +90° around origin -> (-50, -50)
    assert verts[0][0] == -50
    assert round(verts[0][1], 6) == -50


# ---------------------------------------------------------------------------
# ClickManager
# ---------------------------------------------------------------------------


class _FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_click_manager_single_click_returns_none():
    clk = _FakeClock()
    cm = ClickManager(clock=clk)
    assert cm.click("a") is None


def test_click_manager_double_click_within_window():
    clk = _FakeClock()
    cm = ClickManager(clock=clk, window=0.5)
    cm.click("a")
    clk.advance(0.2)
    assert cm.click("a") == "DOUBLE"


def test_click_manager_triple_click_within_window():
    clk = _FakeClock()
    cm = ClickManager(clock=clk, window=0.5)
    cm.click("a")
    clk.advance(0.1)
    cm.click("a")
    clk.advance(0.1)
    assert cm.click("a") == "TRIPLE"


def test_click_manager_outside_window_resets():
    clk = _FakeClock()
    cm = ClickManager(clock=clk, window=0.5)
    cm.click("a")
    clk.advance(1.0)  # outside window
    assert cm.click("a") is None


def test_click_manager_different_objects_break_sequence():
    clk = _FakeClock()
    cm = ClickManager(clock=clk, window=0.5)
    cm.click("a")
    clk.advance(0.1)
    cm.click("b")
    clk.advance(0.1)
    assert cm.click("a") is None
