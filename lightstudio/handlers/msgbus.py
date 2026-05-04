"""msgbus subscription (Step 17).

Ports the ``LayerObjects.active`` subscription from legacy
``light_operators.py``: when a light child mesh / area becomes active in
ANIMATION mode, unhide the corresponding rotation + handle empties so
the user can directly key them. The complementary multiprofile
subscription lives in :mod:`lightstudio.operators.profiles` (it tracks
profile switches, not light selection).

Subscriptions are owned by ``_owner`` (a per-module sentinel) so a
single ``bpy.msgbus.clear_by_owner(_owner)`` cleans up on unregister.
The subscription is re-installed on file load via
:func:`_load_post_resubscribe` (msgbus subscriptions are wiped on
``load_post``).
"""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from ..core.scene_utils import find_light_grp

_owner = object()
_SUBSCRIBE_TO = (bpy.types.LayerObjects, "active")


def _msgbus_callback(*_args) -> None:
    active_object = bpy.context.active_object
    scene = bpy.context.scene
    props = getattr(scene, "LLStudio", None)
    if (
        not active_object
        or props is None
        or not props.initialized
        or props.lls_mode == "NORMAL"
    ):
        return

    if not (
        active_object.name.startswith("LLS_LIGHT_MESH")
        or active_object.name.startswith("LLS_LIGHT_AREA")
    ):
        return

    root = find_light_grp(active_object)
    if root is None or not root.children:
        return
    lls_rotation = root.children[0]
    lls_rotation.hide_viewport = False
    lls_rotation.hide_select = False
    lls_rotation.select_set(True)
    if lls_rotation.children:
        lls_handle = lls_rotation.children[0]
        lls_handle.hide_viewport = False
        lls_handle.hide_select = False
        lls_handle.select_set(True)

    mat = active_object.active_material
    try:
        nodes = mat.node_tree.nodes
        for node in nodes:
            if node.name.startswith("Group"):
                node.select = True
                break
    except AttributeError:
        return


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
