"""Pure-Python widget primitives for the 2D Control Panel modal.

This module is the bpy/gpu-free foundation of step 15. It contains:

* :class:`Vec2` — minimal 2D vector so :class:`Rectangle` works without
  ``mathutils``. Compatible with ``mathutils.Vector`` at the duck-typing
  level (``.x`` / ``.y`` attributes, ``+`` / ``-`` / ``*`` arithmetic)
  so the GPU layer in step 15b can mix and match.
* :class:`Rectangle` — axis-aligned rectangle with rotation, the base
  class for :class:`Panel`, :class:`Button`, :class:`Border`,
  :class:`LightImage` (defined in step 15b).
* :func:`is_in_rect`, :func:`clamp` — geometry helpers.
* Edge/corner hit-test flags ``W_LEFT`` / ``W_RIGHT`` / ``W_TOP`` /
  ``W_BOTTOM`` and :func:`border_touch_point` — pure classification of
  where the cursor sits relative to a rectangle's resize handles. The
  modal operator (step 15c) wraps this with cursor-shape changes.
* :class:`ClickManager` — single/double/triple-click sequencer with an
  injectable clock for tests.

No ``import bpy``, no ``import gpu``, no I/O at import time.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from math import cos, sin

# ---------------------------------------------------------------------------
# Edge/corner hit-test flags (bitmask)
# ---------------------------------------------------------------------------

W_LEFT = 1
W_RIGHT = 2
W_TOP = 4
W_BOTTOM = 8


# ---------------------------------------------------------------------------
# Tiny 2D vector
# ---------------------------------------------------------------------------


class Vec2:
    """Mutable 2D vector. Compatible with ``mathutils.Vector`` duck-typing."""

    __slots__ = ("x", "y")

    def __init__(self, xy: Iterable[float] | tuple[float, float] = (0.0, 0.0)) -> None:
        if hasattr(xy, "x") and hasattr(xy, "y"):
            self.x = float(xy.x)  # type: ignore[union-attr]
            self.y = float(xy.y)  # type: ignore[union-attr]
        else:
            x, y = xy  # type: ignore[misc]
            self.x = float(x)
            self.y = float(y)

    def __iter__(self):
        yield self.x
        yield self.y

    def __repr__(self) -> str:
        return f"Vec2({self.x!r}, {self.y!r})"

    def __eq__(self, other: object) -> bool:
        if not (hasattr(other, "x") and hasattr(other, "y")):
            return NotImplemented
        return self.x == other.x and self.y == other.y  # type: ignore[union-attr]

    def __hash__(self) -> int:
        return hash((self.x, self.y))

    def __add__(self, other) -> Vec2:
        return Vec2((self.x + other.x, self.y + other.y))

    def __sub__(self, other) -> Vec2:
        return Vec2((self.x - other.x, self.y - other.y))

    def __mul__(self, scalar: float) -> Vec2:
        return Vec2((self.x * scalar, self.y * scalar))

    __rmul__ = __mul__

    def __truediv__(self, scalar: float) -> Vec2:
        return Vec2((self.x / scalar, self.y / scalar))

    def __iadd__(self, other) -> Vec2:
        self.x += other.x
        self.y += other.y
        return self

    def __isub__(self, other) -> Vec2:
        self.x -= other.x
        self.y -= other.y
        return self


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def clamp(minimum: float, x: float, maximum: float) -> float:
    """Clamp ``x`` to the inclusive range ``[minimum, maximum]``."""
    return max(minimum, min(x, maximum))


def is_in_rect(rect: Rectangle, loc) -> bool:
    """Return True when ``loc`` (anything with ``.x`` / ``.y``) is inside ``rect``.

    Uses the rectangle's *unrotated* axis-aligned bounding box — this
    matches the legacy hit-test which is intentionally rotation-agnostic
    for click detection on the panel UI.
    """
    return (
        rect.point_lt.x <= loc.x <= rect.point_rb.x
        and rect.point_rb.y <= loc.y <= rect.point_lt.y
    )


# ---------------------------------------------------------------------------
# Rectangle
# ---------------------------------------------------------------------------


class Rectangle:
    """Axis-aligned rectangle with optional rotation around its centre.

    ``point_lt`` is the top-left corner (max y, min x), ``point_rb`` is
    the bottom-right (min y, max x). Width/height are derived; setting
    them resizes around the centre. ``loc`` is the centre point.
    """

    def __init__(self, start_point, width: float, height: float) -> None:
        self.point_lt = Vec2((
            min(start_point.x, start_point.x + width),
            max(start_point.y, start_point.y + height),
        ))
        self.point_rb = Vec2((
            max(start_point.x, start_point.x + width),
            min(start_point.y, start_point.y + height),
        ))
        self.rot: float = 0.0

    # -- centre ----------------------------------------------------------

    @property
    def loc(self) -> Vec2:
        return (self.point_lt + self.point_rb) / 2

    @loc.setter
    def loc(self, loc) -> None:
        d = Vec2((loc.x, loc.y)) - self.loc
        self.point_lt += d
        self.point_rb += d

    # -- size ------------------------------------------------------------

    @property
    def width(self) -> float:
        return self.point_rb.x - self.point_lt.x

    @width.setter
    def width(self, width: float) -> None:
        d = width - self.width
        self.point_lt.x -= d / 2
        self.point_rb.x = self.point_lt.x + width

    @property
    def height(self) -> float:
        return self.point_lt.y - self.point_rb.y

    @height.setter
    def height(self, height: float) -> None:
        d = height - self.height
        self.point_lt.y += d / 2
        self.point_rb.y = self.point_lt.y - height

    # -- geometry --------------------------------------------------------

    def get_verts(self) -> tuple[list[float], list[float], list[float], list[float]]:
        """Return the four corner vertices (lt, lb, rt, rb), rotation applied."""

        def rotate(x1: float, y1: float, offset: Vec2) -> list[float]:
            x1 -= offset.x
            y1 -= offset.y
            x2 = cos(self.rot) * x1 - sin(self.rot) * y1
            y2 = sin(self.rot) * x1 + cos(self.rot) * y1
            x2 += offset.x
            y2 += offset.y
            return [x2, y2]

        loc = self.loc  # cache to avoid recomputing per corner
        return (
            rotate(self.point_lt.x, self.point_lt.y, loc),
            rotate(self.point_lt.x, self.point_rb.y, loc),
            rotate(self.point_rb.x, self.point_lt.y, loc),
            rotate(self.point_rb.x, self.point_rb.y, loc),
        )

    def get_tex_coords(self) -> tuple[list[int], list[int], list[int], list[int]]:
        return ([0, 1], [0, 0], [1, 1], [1, 0])

    def move(self, loc_diff) -> None:
        """Translate by ``loc_diff``, clamped to the parent panel if any."""
        rect = self.panel if hasattr(self, "panel") else self  # type: ignore[attr-defined]
        new_loc = self.loc + loc_diff
        new_loc.x = clamp(rect.point_lt.x, new_loc.x, rect.point_rb.x)
        new_loc.y = clamp(rect.point_rb.y, new_loc.y, rect.point_lt.y)
        self.loc = new_loc


# ---------------------------------------------------------------------------
# Edge/corner hit-test
# ---------------------------------------------------------------------------


def border_touch_point(rect: Rectangle, x: float, y: float, threshold: int = 5) -> int:
    """Classify which border/corner of ``rect`` the point ``(x, y)`` touches.

    Returns a bitmask combining ``W_LEFT`` / ``W_RIGHT`` / ``W_TOP`` /
    ``W_BOTTOM``. ``0`` means the point is outside the resize-handle
    region. Two flags combined indicate a corner.

    This is a pure classification — the modal operator is responsible
    for translating the result into a cursor-shape change.
    """
    touch_point = 0

    if rect.point_rb.y - threshold <= y <= rect.point_lt.y + threshold:
        if rect.point_lt.x - threshold <= x < rect.point_lt.x + threshold:
            touch_point |= W_LEFT
        elif rect.point_rb.x - threshold < x <= rect.point_rb.x + threshold:
            touch_point |= W_RIGHT

    if rect.point_lt.x - threshold <= x <= rect.point_rb.x + threshold:
        if rect.point_lt.y - threshold < y <= rect.point_lt.y + threshold:
            touch_point |= W_TOP
        elif rect.point_rb.y - threshold <= y < rect.point_rb.y + threshold:
            touch_point |= W_BOTTOM

    return touch_point


# ---------------------------------------------------------------------------
# Click sequencer
# ---------------------------------------------------------------------------


class ClickManager:
    """Sequence single/double/triple clicks on identifiable objects.

    Successive clicks on the same ``object`` within ``window`` seconds
    return ``"DOUBLE"`` and ``"TRIPLE"``; otherwise :meth:`click`
    returns ``None`` (caller treats as single-click).

    The clock is injectable for tests via the ``clock`` constructor
    argument; defaults to :func:`time.time`.
    """

    def __init__(self, clock: Callable[[], float] = time.time, window: float = 0.5) -> None:
        self._clock = clock
        self._window = window
        self.times: list[float] = [0.0, 0.0, 0.0]
        self.objects: list[object] = [None, None, None]

    def click(self, obj: object) -> str | None:
        self.times.append(self._clock())
        self.objects.append(obj)
        if len(self.times) > 3:
            del self.times[0]
            del self.objects[0]

        if (
            self.objects[0] == self.objects[1] == self.objects[2]
            and self.times[2] - self.times[0] <= self._window
        ):
            return "TRIPLE"
        if (
            self.objects[1] == self.objects[2]
            and self.times[2] - self.times[1] <= self._window
        ):
            return "DOUBLE"
        return None
