"""Blender-coupled helpers for navigating the LLS scene hierarchy.

These functions all touch :mod:`bpy` and so are kept out of the
``core/common.py`` pure layer (step 8). They were extracted from the
legacy ``common.py`` (``get_lls_collection``, ``get_collection``,
``find_view_layer``, ``isFamily``, ``family``, ``findLightGrp``,
``findLightProfileObject``, ``llscol_profilecol``,
``llscol_profilecol_profile_handle``, ``duplicate_collection``,
``replace_link``) so the ported operators in step 11+ can share one
canonical implementation.
"""

from __future__ import annotations

from collections.abc import Iterable

import bpy

from .common import LIGHT_GROUP_PREFIX, LLS_PREFIX, ROOT_PREFIX

_PROFILE_PREFIX = "LLS_PROFILE"
_LIGHT_HANDLE_PREFIX = "LLS_LIGHT_HANDLE"
_LIGHT_COLLECTION_PREFIX = "LLS_Light"


def get_lls_collection(context: bpy.types.Context) -> bpy.types.Collection | None:
    """Return the top-level ``LLS`` collection in the scene, or ``None``."""
    for col in context.scene.collection.children:
        if col.name.startswith("LLS"):
            return col
    return None


def get_collection(obj: bpy.types.Object) -> bpy.types.Collection | None:
    """Return the first collection an object is linked to whose name
    starts with ``LLS``."""
    for c in obj.users_collection:
        if c.name.startswith("LLS"):
            return c
    return None


def find_view_layer(
    collection: bpy.types.Collection,
    layer_collection: bpy.types.LayerCollection,
) -> bpy.types.LayerCollection | None:
    """Walk a ``LayerCollection`` tree, returning the layer that wraps
    ``collection``."""
    idx = layer_collection.children.find(collection.name)
    if idx >= 0:
        return layer_collection.children[idx]
    for child in layer_collection.children:
        found = find_view_layer(collection, child)
        if found is not None:
            return found
    return None


def is_family(obj: bpy.types.Object | None) -> bool:
    """Return True if ``obj`` is part of an LLS hierarchy."""
    if obj is None:
        obj = bpy.context.view_layer.objects.active
        if obj is None:
            return False
    if obj.name.startswith(ROOT_PREFIX):
        return True
    if not obj.name.startswith(LLS_PREFIX):
        return False
    cur = obj
    while cur.parent:
        cur = cur.parent
        if cur.name.startswith(ROOT_PREFIX):
            return True
    return False


def family(obj: bpy.types.Object) -> list[bpy.types.Object]:
    """Return ``obj`` plus every descendant (children of children…)."""
    result: list[bpy.types.Object] = [obj]

    def _rec(parent: bpy.types.Object) -> None:
        for child in parent.children:
            result.append(child)
            _rec(child)

    _rec(obj)
    return result


def find_light_grp(obj: bpy.types.Object) -> bpy.types.Object | None:
    """Walk ancestors until an ``LLS_LIGHT.*`` object is found."""
    cur: bpy.types.Object | None = obj
    while cur and cur.parent:
        cur = cur.parent
        if cur.name.startswith(LIGHT_GROUP_PREFIX):
            return cur
    return None


def find_light_profile_object(obj: bpy.types.Object) -> bpy.types.Object | None:
    """Walk ancestors until an ``LLS_PROFILE.*`` object is found."""
    if obj.name.startswith(_PROFILE_PREFIX):
        return obj
    cur: bpy.types.Object | None = obj
    while cur and cur.parent:
        cur = cur.parent
        if cur.name.startswith(_PROFILE_PREFIX + "."):
            return cur
    return None


def llscol_profilecol(
    context: bpy.types.Context,
) -> tuple[bpy.types.Collection | None, bpy.types.Collection | None]:
    """Return (LLS root collection, active profile collection) or (None, None)."""
    props = context.scene.LLStudio
    if not len(props.profile_list):
        return (None, None)
    lls_collection = get_lls_collection(context)
    try:
        empty_name = props.profile_list[props.profile_list_index].empty_name
        profile_collection = get_collection(bpy.data.objects[empty_name])
    except (IndexError, KeyError):
        return (lls_collection, None)
    return (lls_collection, profile_collection)


def llscol_profilecol_profile_handle(
    context: bpy.types.Context,
) -> tuple[
    bpy.types.Collection,
    bpy.types.Collection,
    bpy.types.Object,
    bpy.types.Object,
]:
    """Return (LLS collection, profile collection, profile empty, profile handle).

    Raises ``IndexError`` / ``KeyError`` if any expected hierarchy piece
    is missing — callers should be guarded by an operator ``poll``.
    """
    props = context.scene.LLStudio
    profile_empty_name = props.profile_list[props.profile_list_index].empty_name
    lls_collection = get_lls_collection(context)
    if lls_collection is None:
        raise KeyError("LLS collection not found")
    profile_collection = get_collection(bpy.data.objects[profile_empty_name])
    if profile_collection is None:
        raise KeyError("profile collection not found")
    profile = next(
        ob for ob in profile_collection.objects if ob.name.startswith(_PROFILE_PREFIX)
    )
    handle = next(ob for ob in profile.children if ob.name.startswith("LLS_HANDLE"))
    return lls_collection, profile_collection, profile, handle


def replace_link(obj: bpy.types.Object | bpy.types.Collection, collection_name: str) -> None:
    """Move ``obj`` from its current scene-root link to live inside
    ``bpy.data.collections[collection_name]``."""
    if isinstance(obj, bpy.types.Collection):
        bpy.context.scene.collection.children.unlink(
            bpy.context.scene.collection.children[obj.name]
        )
        bpy.data.collections[collection_name].children.link(obj)
    else:
        obj.users_collection[0].objects.unlink(obj)
        bpy.data.collections[collection_name].objects.link(obj)


def duplicate_collection(
    collection: bpy.types.Collection,
    parent_collection: bpy.types.Collection | None,
) -> bpy.types.Collection:
    """Recursively duplicate ``collection`` (objects, meshes, materials).

    Preserves parent relationships and reparents ``LLS_LIGHT_HANDLE``
    constraints to the duplicated profile handle when present.
    """
    new_names: dict[str, bpy.types.Object] = {}
    matrix_data: dict[str, dict[str, object]] = {}
    profile_handle_iter: Iterable[bpy.types.Object] = (
        obj for obj in collection.objects if obj.name.startswith("LLS_HANDLE")
    )
    profile_handle = next(profile_handle_iter, None)

    def rec_dup(
        col: bpy.types.Collection,
        parent_col: bpy.types.Collection | None,
    ) -> bpy.types.Collection:
        new_collection = bpy.data.collections.new(col.name)
        new_collection.use_fake_user = True
        for obj in col.objects:
            new_obj = obj.copy()
            new_names[obj.name] = new_obj
            matrix_data[new_obj.name] = {
                "matrix_basis": obj.matrix_basis.copy(),
                "matrix_parent_inverse": obj.matrix_parent_inverse.copy(),
            }
            if new_obj.data:
                new_obj.data = obj.data.copy()
            for slot in new_obj.material_slots:
                if slot.material is not None:
                    slot.material = slot.material.copy()
            new_obj.parent = obj.parent
            new_collection.objects.link(new_obj)

        for obj in new_collection.objects:
            if obj.parent and obj.parent.name in new_names:
                obj.parent = new_names[obj.parent.name]
                obj.matrix_basis = matrix_data[obj.name]["matrix_basis"]  # type: ignore[assignment]
                obj.matrix_parent_inverse = matrix_data[obj.name][  # type: ignore[assignment]
                    "matrix_parent_inverse"
                ]
                if profile_handle and obj.name.startswith(_LIGHT_HANDLE_PREFIX):
                    constraint = obj.constraints.get("Child Of")
                    if constraint is not None:
                        constraint.target = new_names[profile_handle.name]
                        constraint.inverse_matrix.identity()

        if parent_col is not None:
            parent_col.children.link(new_collection)

        for child in col.children[:]:
            rec_dup(child, new_collection)

        return new_collection

    return rec_dup(collection, parent_collection)


def update_light_list_set(
    context: bpy.types.Context, profile_idx: int | None = None
) -> None:
    """Resync ``Scene.LLStudio.light_list`` with the actual scene hierarchy.

    Ported (simplified) from legacy ``light_list.update_light_list_set``;
    drops the ``salvage_data`` / ``light_from_dict`` repair branch (those
    arrive in step 12 alongside the import operator).
    """
    props = context.scene.LLStudio
    if not len(props.profile_list):
        props.light_list.clear()
        return

    idx = props.profile_list_index if profile_idx is None else profile_idx
    if idx >= len(props.profile_list):
        props.light_list.clear()
        return

    item = props.profile_list[idx]
    empty = bpy.data.objects.get(item.empty_name)
    if empty is None or not empty.users_collection:
        props.light_list.clear()
        return

    profile_collection = empty.users_collection[0]
    if not (item.enabled or not props.profile_multimode):
        return

    props.light_list.clear()
    handles: list[bpy.types.Object] = []
    for col in profile_collection.children:
        for ob in col.objects:
            if ob.name.startswith(_LIGHT_HANDLE_PREFIX):
                handles.append(ob)
    handles.sort(key=lambda m: m.LLStudio.order_index)
    layer_root = context.view_layer.layer_collection
    for i, handle in enumerate(handles):
        handle.LLStudio.order_index = i
        ll = props.light_list.add()
        ll.handle_name = handle.name
        ll.name = handle.LLStudio.light_name or f"Light {i}"

        # Restore Basic/Advanced visibility from the persisted LLStudio.type
        # on the light handle (re-linking a profile collection rebuilds
        # the LayerCollection tree with default exclude=False, so without
        # this both sub-collections would appear).
        if not handle.users_collection:
            continue
        light_collection = handle.users_collection[0]
        light_view = find_view_layer(light_collection, layer_root)
        if light_view is None or light_view.exclude:
            continue
        basic = next(
            (
                c
                for c in light_collection.children
                if c.name.startswith("LLS_Basic")
            ),
            None,
        )
        advanced = next(
            (
                c
                for c in light_collection.children
                if c.name.startswith("LLS_Advanced")
            ),
            None,
        )
        if basic is None or advanced is None:
            continue
        basic_view = find_view_layer(basic, layer_root)
        advanced_view = find_view_layer(advanced, layer_root)
        if basic_view is None or advanced_view is None:
            continue
        if handle.LLStudio.type == "ADVANCED":
            basic_view.exclude = True
            advanced_view.exclude = False
        else:
            basic_view.exclude = False
            advanced_view.exclude = True
