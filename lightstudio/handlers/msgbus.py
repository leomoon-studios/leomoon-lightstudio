"""msgbus subscription (Step 17).

Tracks active-object changes that affect LightStudio selection-aware UI.
The complementary multiprofile subscription lives in
:mod:`lightstudio.operators.profiles` (it tracks profile switches, not
light selection).

Subscriptions are owned by ``_owner`` (a per-module sentinel) so a
single ``bpy.msgbus.clear_by_owner(_owner)`` cleans up on unregister.
The subscription is re-installed on file load via
:func:`_load_post_resubscribe` (msgbus subscriptions are wiped on
``load_post``).
"""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from ..core.selected_light import retarget_pin_to_active_light

_owner = object()
_SUBSCRIBE_TO = (bpy.types.LayerObjects, "active")


def _msgbus_callback(*_args) -> None:
    scene = bpy.context.scene
    props = getattr(scene, "LLStudio", None)
    if props is not None and props.initialized:
        retarget_pin_to_active_light(bpy.context)


def _subscribe() -> None:
    bpy.msgbus.subscribe_rna(
        key=_SUBSCRIBE_TO,
        owner=_owner,
        args=(),
        notify=_msgbus_callback,
    )


@persistent
def _load_post_resubscribe(_dummy) -> None:
    _subscribe()


def register() -> None:
    _subscribe()
    if _load_post_resubscribe not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post_resubscribe)


def unregister() -> None:
    if _load_post_resubscribe in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post_resubscribe)
    bpy.msgbus.clear_by_owner(_owner)
