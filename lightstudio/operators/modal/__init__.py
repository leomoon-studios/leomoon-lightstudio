"""Modal Control Panel — 2D GPU overlay (steps 15b-15d).

* :mod:`.gpu_layer` (15b) — shaders, UBO, draw primitives.
* :mod:`.control_panel` (15c) — modal operator + Grab/Scale/Rotate
  sub-operators + reset op + G/S/R keymaps.
* (15d) — teardown hardening + draw-handler tracking.
"""

from __future__ import annotations

from . import control_panel

# Rotation precision factor used by the Rotate operator (legacy
# ``operators/__init__.AREA_DEFAULT_SIZE``).
AREA_DEFAULT_SIZE = 9


def register() -> None:
    control_panel.register()


def unregister() -> None:
    control_panel.unregister()
