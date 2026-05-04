"""LeoMoon LightStudio — Blender 5.1+ extension."""

import bpy

from . import handlers, operators, properties, ui
from .core.log import log
from .ui import panels as _panels


def _deferred_panel_register() -> float | None:
    """Register the side-panel classes on the next event-loop tick.

    When the extension is installed/enabled while a Blender session is
    already running, panels registered with a brand-new ``bl_category``
    ("LightStudio") don't appear in the 3D-View sidebar until each
    VIEW_3D area's UI region rebuilds its tab list. Calling
    ``bpy.utils.register_class`` for those panels from a one-shot timer
    forces Blender to treat them as a fresh runtime registration, which
    inserts the LightStudio tab without the user having to disable+
    re-enable the addon (or restart Blender).
    """
    _panels.register()
    # Nudge every open 3D-View UI region so the new tab paints right
    # away on the current frame.
    wm = bpy.context.window_manager
    if wm is not None:
        for window in wm.windows:
            for area in window.screen.areas:
                if area.type != "VIEW_3D":
                    continue
                for region in area.regions:
                    if region.type == "UI":
                        region.tag_redraw()
    return None  # one-shot timer


def register() -> None:
    properties.register()
    operators.register()
    # ui.register() registers preview list, UILists, panels, preferences.
    # We split panel registration off so it can run on the next tick —
    # see _deferred_panel_register() above for the rationale.
    ui._register_without_panels()
    handlers.register()
    if not bpy.app.timers.is_registered(_deferred_panel_register):
        bpy.app.timers.register(_deferred_panel_register, first_interval=0)
    log("extension loaded")


def unregister() -> None:
    if bpy.app.timers.is_registered(_deferred_panel_register):
        bpy.app.timers.unregister(_deferred_panel_register)
    handlers.unregister()
    ui.unregister()
    operators.unregister()
    properties.unregister()
    log("extension unloaded")
