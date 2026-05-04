"""``WindowManager.lls_tex_previews`` enum + bpy.utils.previews collection.

Ports legacy ``light_preview_list`` to use :mod:`lightstudio.core.textures`
for the disk scan (lazy + mtime-cached). The preview thumbnails
themselves are still produced by ``bpy.utils.previews`` since that is
the only way to feed ``template_icon_view``.
"""

from __future__ import annotations

import os

import bpy
import bpy.utils.previews
from bpy.props import EnumProperty

from ..core.paths import TEXTURES_DIR
from ..core.textures import scan as scan_textures

_preview_collections: dict[str, object] = {}


def _enum_items(self, context):
    if context is None:
        return []
    pcoll = _preview_collections.get("main")
    if pcoll is None:
        return []
    try:
        dir_mtime = TEXTURES_DIR.stat().st_mtime
    except FileNotFoundError:
        return []
    if pcoll.initiated and dir_mtime <= pcoll.dir_update_time:
        return pcoll.tex_previews
    pcoll.dir_update_time = dir_mtime
    pcoll.clear()

    enum_items: list[tuple[str, str, str, int, int]] = []
    for i, path in enumerate(scan_textures()):
        thumb = pcoll.load(str(path), str(path), "IMAGE", True)
        basename = path.stem
        enum_items.append((path.name, basename, path.name, thumb.icon_id, i))

    pcoll.tex_previews = enum_items
    pcoll.initiated = True
    return pcoll.tex_previews


def _active_light_mesh():
    from ..core.scene_utils import family, find_light_grp

    obj = bpy.context.active_object
    if obj is None:
        return None
    lg = find_light_grp(obj)
    if lg is None:
        return None
    for child in family(lg):
        if child.name.startswith("LLS_LIGHT_MESH"):
            return child
    return None


def _enum_get(_wm) -> int:
    light = _active_light_mesh()
    if light is None or not light.active_material:
        return -1
    nodes = light.active_material.node_tree.nodes
    if "Light Texture" not in nodes:
        return -1
    image = nodes["Light Texture"].image
    if image is None:
        return -1
    tex = os.path.split(image.filepath)[1]
    pcoll = _preview_collections.get("main")
    if pcoll is None:
        return -1
    for i, entry in enumerate(pcoll.tex_previews):
        if entry[0] == tex:
            return i
    return -1


def _enum_set(_wm, context: int) -> None:
    pcoll = _preview_collections.get("main")
    if pcoll is None:
        return
    name = pcoll.tex_previews[context][0]
    light = _active_light_mesh()
    if light is None or not light.active_material:
        return
    light.active_material.node_tree.nodes["Light Texture"].image = (
        bpy.data.images.load(str(TEXTURES_DIR / name), check_existing=True)
    )


def register() -> None:
    bpy.types.WindowManager.lls_tex_previews = EnumProperty(
        items=_enum_items,
        get=_enum_get,
        set=_enum_set,
    )
    pcoll = bpy.utils.previews.new()
    pcoll.tex_previews = ()
    pcoll.initiated = False
    try:
        pcoll.dir_update_time = TEXTURES_DIR.stat().st_mtime
    except FileNotFoundError:
        pcoll.dir_update_time = 0.0
    _preview_collections["main"] = pcoll


def unregister() -> None:
    if hasattr(bpy.types.WindowManager, "lls_tex_previews"):
        del bpy.types.WindowManager.lls_tex_previews
    for pcoll in _preview_collections.values():
        try:
            pcoll.clear()
            bpy.utils.previews.remove(pcoll)
        except Exception:  # noqa: BLE001
            pass
    _preview_collections.clear()
