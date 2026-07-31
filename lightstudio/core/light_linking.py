"""Blender-coupled helpers for native Light Linking support.

This module probes Blender capability, resolves LightStudio's existing
light hierarchy, and syncs handle-level Light Linking properties to
Blender's native light-linking collection API.
"""

from __future__ import annotations

import bpy

from .common import LIGHT_AREA_PREFIX, LIGHT_GROUP_PREFIX, LIGHT_HANDLE_PREFIX, LIGHT_MESH_PREFIX
from .scene_utils import family

_LINK_STATE_VALUES = {"INCLUDE", "EXCLUDE"}
_CATEGORY_VALUES = {"LIGHT", "SHADOW"}
_INTERNAL_COLLECTION_PREFIX = "LLS_LIGHT_LINKING"

RECEIVER_WRAPPER = "receiver"
BLOCKER_WRAPPER = "blocker"
LIGHT_INCLUDE_BUCKET = "light_include"
LIGHT_EXCLUDE_BUCKET = "light_exclude"
SHADOW_INCLUDE_BUCKET = "shadow_include"
SHADOW_EXCLUDE_BUCKET = "shadow_exclude"

_COLLECTION_LABELS = {
    RECEIVER_WRAPPER: "Receiver",
    BLOCKER_WRAPPER: "Blocker",
    LIGHT_INCLUDE_BUCKET: "Light.In",
    LIGHT_EXCLUDE_BUCKET: "Light.Ex",
    SHADOW_INCLUDE_BUCKET: "Shadow.In",
    SHADOW_EXCLUDE_BUCKET: "Shadow.Ex",
}
_PROPERTY_BUCKETS = (
    ("light_linking_include_targets", LIGHT_INCLUDE_BUCKET),
    ("light_linking_exclude_targets", LIGHT_EXCLUDE_BUCKET),
    ("shadow_linking_include_targets", SHADOW_INCLUDE_BUCKET),
    ("shadow_linking_exclude_targets", SHADOW_EXCLUDE_BUCKET),
)


def _rna_has_property(rna_type: type | None, prop_name: str) -> bool:
    if rna_type is None:
        return False
    return prop_name in rna_type.bl_rna.properties


def has_native_light_linking_api() -> bool:
    """Return whether Blender exposes emitter-level light-linking slots."""
    object_light_linking = getattr(bpy.types, "ObjectLightLinking", None)
    return (
        _rna_has_property(bpy.types.Object, "light_linking")
        and _rna_has_property(object_light_linking, "receiver_collection")
        and _rna_has_property(object_light_linking, "blocker_collection")
    )


def has_native_light_linking_row_state() -> bool:
    """Return whether Blender exposes include/exclude state for linked rows."""
    collection_light_linking = getattr(bpy.types, "CollectionLightLinking", None)
    if not (
        _rna_has_property(bpy.types.CollectionObject, "light_linking")
        and _rna_has_property(bpy.types.CollectionChild, "light_linking")
        and _rna_has_property(collection_light_linking, "link_state")
    ):
        return False

    link_state = collection_light_linking.bl_rna.properties["link_state"]
    values = {item.identifier for item in link_state.enum_items}
    return _LINK_STATE_VALUES.issubset(values)


def resolve_light_handle(obj: bpy.types.Object | None) -> bpy.types.Object | None:
    """Resolve any selected object in one LightStudio light to its handle.

    Returns ``None`` for unrelated objects, malformed hierarchies, or
    ambiguous selections such as a profile/root object.
    """
    if obj is None:
        return None
    if obj.name.startswith(LIGHT_HANDLE_PREFIX):
        return obj

    cur = obj.parent
    while cur is not None:
        if cur.name.startswith(LIGHT_HANDLE_PREFIX):
            return cur
        if cur.name.startswith(LIGHT_GROUP_PREFIX):
            return _handle_descendant(cur)
        cur = cur.parent

    if obj.name.startswith(LIGHT_GROUP_PREFIX):
        return _handle_descendant(obj)
    return None


def resolve_light_emitters(
    handle: bpy.types.Object | None,
) -> tuple[bpy.types.Object | None, bpy.types.Object | None]:
    """Return ``(basic_area, advanced_mesh)`` emitters for a light handle."""
    if handle is None or not handle.name.startswith(LIGHT_HANDLE_PREFIX):
        return (None, None)

    basic_area = None
    advanced_mesh = None
    for obj in family(handle):
        if basic_area is None and obj.name.startswith(LIGHT_AREA_PREFIX):
            basic_area = obj
        elif advanced_mesh is None and obj.name.startswith(LIGHT_MESH_PREFIX):
            advanced_mesh = obj
        if basic_area is not None and advanced_mesh is not None:
            break
    return (basic_area, advanced_mesh)


def is_valid_lightstudio_light(obj: bpy.types.Object | None) -> bool:
    """Return whether ``obj`` resolves to a handle with both native emitters."""
    handle = resolve_light_handle(obj)
    basic_area, advanced_mesh = resolve_light_emitters(handle)
    return basic_area is not None and advanced_mesh is not None


def ensure_internal_collections(
    handle: bpy.types.Object,
) -> dict[str, bpy.types.Collection]:
    """Return this light's internal native wrappers and logical buckets.

    The returned mapping contains two native API wrappers, ``receiver`` and
    ``blocker``, plus four logical buckets: ``light_include``,
    ``light_exclude``, ``shadow_include``, and ``shadow_exclude``.
    """
    collections = _internal_collections(handle, create=True)
    if collections is None:
        raise RuntimeError("failed to create LightStudio light-linking collections")
    return collections


def assign_target_to_bucket(
    handle: bpy.types.Object,
    category: str,
    mode: str,
    target: bpy.types.Object | bpy.types.Collection | None,
) -> None:
    """Link ``target`` into the matching per-light bucket.

    ``category`` is ``LIGHT`` for receiver light linking or ``SHADOW`` for
    shadow/blocker linking. ``mode`` is Blender's native ``INCLUDE`` or
    ``EXCLUDE`` row state. The target is removed from the opposite bucket
    in the same category so the same target has one active mode per
    category.
    """
    if target is None:
        return
    _validate_category_and_mode(category, mode)
    collections = ensure_internal_collections(handle)
    include_bucket, exclude_bucket = _category_buckets(collections, category)
    destination = include_bucket if mode == "INCLUDE" else exclude_bucket
    source = exclude_bucket if mode == "INCLUDE" else include_bucket

    _unlink_target(source, target)
    _link_target(destination, target)


def set_light_linking_target_mode(
    handle: bpy.types.Object,
    target: bpy.types.Object | bpy.types.Collection | None,
    mode: str,
) -> None:
    """Move a Light Linking target row to ``INCLUDE`` or ``EXCLUDE``."""
    assign_target_to_bucket(handle, "LIGHT", mode, target)


def set_shadow_linking_target_mode(
    handle: bpy.types.Object,
    target: bpy.types.Object | bpy.types.Collection | None,
    mode: str,
) -> None:
    """Move a Shadow Linking target row to ``INCLUDE`` or ``EXCLUDE``."""
    assign_target_to_bucket(handle, "SHADOW", mode, target)


def sync_light_linking_properties(handle: bpy.types.Object) -> None:
    """Rebuild internal buckets from ``handle.LLStudio`` target-list properties."""
    if not hasattr(handle, "LLStudio"):
        sync_native_light_linking(handle)
        return

    has_targets = _has_property_targets(handle)
    collections = _internal_collections(handle, create=has_targets)
    if collections is None:
        clear_native_receiver_assignment(handle)
        clear_native_shadow_assignment(handle)
        return

    for key in (
        LIGHT_INCLUDE_BUCKET,
        LIGHT_EXCLUDE_BUCKET,
        SHADOW_INCLUDE_BUCKET,
        SHADOW_EXCLUDE_BUCKET,
    ):
        _unlink_all_direct_targets(collections[key])

    if has_targets:
        props = handle.LLStudio
        for prop_name, bucket_key in _PROPERTY_BUCKETS:
            bucket = collections[bucket_key]
            for row in getattr(props, prop_name):
                target = _target_from_row(row)
                if target is not None:
                    _link_target(bucket, target)

    sync_native_light_linking(handle)


def add_light_linking_target_row(
    handle: bpy.types.Object,
    category: str,
    mode: str,
    target: bpy.types.Object | bpy.types.Collection | None,
) -> bpy.types.PropertyGroup | None:
    """Add a property row for ``target`` and sync both native emitters."""
    if target is None:
        return None
    _validate_category_and_mode(category, mode)
    row = getattr(handle.LLStudio, _target_list_property_name(category, mode)).add()
    _set_row_target(row, target)
    sync_light_linking_properties(handle)
    return row


def remove_light_linking_target_row(
    handle: bpy.types.Object,
    category: str,
    mode: str,
    index: int,
) -> None:
    """Remove a property row and sync both native emitters."""
    _validate_category_and_mode(category, mode)
    rows = getattr(handle.LLStudio, _target_list_property_name(category, mode))
    if 0 <= index < len(rows):
        rows.remove(index)
        sync_light_linking_properties(handle)


def move_light_linking_target_row_mode(
    handle: bpy.types.Object,
    category: str,
    target: bpy.types.Object | bpy.types.Collection | None,
    mode: str,
) -> None:
    """Move a property row target between ``INCLUDE`` and ``EXCLUDE`` lists."""
    if target is None:
        return
    _validate_category_and_mode(category, mode)
    include_name = _target_list_property_name(category, "INCLUDE")
    exclude_name = _target_list_property_name(category, "EXCLUDE")
    for prop_name in (include_name, exclude_name):
        _remove_target_rows(getattr(handle.LLStudio, prop_name), target)
    row = getattr(handle.LLStudio, _target_list_property_name(category, mode)).add()
    _set_row_target(row, target)
    sync_light_linking_properties(handle)


def copy_light_linking_properties(
    source_handle: bpy.types.Object,
    destination_handle: bpy.types.Object,
) -> None:
    """Copy Light Linking target rows from one handle to another and sync."""
    if not (hasattr(source_handle, "LLStudio") and hasattr(destination_handle, "LLStudio")):
        return

    for prop_name, _bucket_key in _PROPERTY_BUCKETS:
        source_rows = getattr(source_handle.LLStudio, prop_name)
        destination_rows = getattr(destination_handle.LLStudio, prop_name)
        destination_rows.clear()
        for source_row in source_rows:
            target = _target_from_row(source_row)
            row = destination_rows.add()
            row.target_type = source_row.target_type
            if isinstance(target, bpy.types.Collection):
                row.collection_target = target
            elif isinstance(target, bpy.types.Object):
                row.object_target = target

    sync_light_linking_properties(destination_handle)


def sync_native_light_linking(handle: bpy.types.Object) -> None:
    """Build native receiver/blocker wrappers from buckets and apply emitters."""
    collections = _internal_collections(handle, create=False)
    if collections is None:
        clear_native_receiver_assignment(handle)
        clear_native_shadow_assignment(handle)
        return

    receiver_wrapper = collections[RECEIVER_WRAPPER]
    blocker_wrapper = collections[BLOCKER_WRAPPER]
    has_light_targets = _bucket_has_targets(collections[LIGHT_INCLUDE_BUCKET]) or _bucket_has_targets(
        collections[LIGHT_EXCLUDE_BUCKET]
    )
    has_shadow_targets = _bucket_has_targets(
        collections[SHADOW_INCLUDE_BUCKET]
    ) or _bucket_has_targets(collections[SHADOW_EXCLUDE_BUCKET])

    if has_light_targets:
        _build_native_wrapper(
            receiver_wrapper,
            collections[LIGHT_INCLUDE_BUCKET],
            collections[LIGHT_EXCLUDE_BUCKET],
        )
    else:
        _unlink_all_direct_targets(receiver_wrapper)

    if has_shadow_targets:
        _build_native_wrapper(
            blocker_wrapper,
            collections[SHADOW_INCLUDE_BUCKET],
            collections[SHADOW_EXCLUDE_BUCKET],
        )
    else:
        _unlink_all_direct_targets(blocker_wrapper)

    apply_native_wrappers(
        handle,
        receiver_wrapper if has_light_targets else None,
        blocker_wrapper if has_shadow_targets else None,
    )


def apply_native_wrappers(
    handle: bpy.types.Object,
    receiver_wrapper: bpy.types.Collection | None,
    blocker_wrapper: bpy.types.Collection | None,
) -> None:
    """Apply native receiver/blocker wrappers to both LightStudio emitters."""
    basic_area, advanced_mesh = resolve_light_emitters(handle)
    for emitter in (basic_area, advanced_mesh):
        if emitter is None or not hasattr(emitter, "light_linking"):
            continue
        emitter.light_linking.receiver_collection = receiver_wrapper
        emitter.light_linking.blocker_collection = blocker_wrapper


def clear_native_receiver_assignment(handle: bpy.types.Object) -> None:
    """Clear native receiver collection assignment on both emitters."""
    basic_area, advanced_mesh = resolve_light_emitters(handle)
    for emitter in (basic_area, advanced_mesh):
        if emitter is not None and hasattr(emitter, "light_linking"):
            emitter.light_linking.receiver_collection = None


def clear_native_shadow_assignment(handle: bpy.types.Object) -> None:
    """Clear native blocker collection assignment on both emitters."""
    basic_area, advanced_mesh = resolve_light_emitters(handle)
    for emitter in (basic_area, advanced_mesh):
        if emitter is not None and hasattr(emitter, "light_linking"):
            emitter.light_linking.blocker_collection = None


def _handle_descendant(obj: bpy.types.Object) -> bpy.types.Object | None:
    handles = [child for child in family(obj) if child.name.startswith(LIGHT_HANDLE_PREFIX)]
    if len(handles) == 1:
        return handles[0]
    return None


def _ensure_collection(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
    collection.use_fake_user = True
    return collection


def _internal_collections(
    handle: bpy.types.Object,
    create: bool,
) -> dict[str, bpy.types.Collection] | None:
    collections: dict[str, bpy.types.Collection] = {}
    for key in _COLLECTION_LABELS:
        name = _internal_collection_name(handle, key)
        collection = _ensure_collection(name) if create else bpy.data.collections.get(name)
        if collection is None:
            return None
        collections[key] = collection
    return collections


def _internal_collection_name(handle: bpy.types.Object, key: str) -> str:
    return f"{_INTERNAL_COLLECTION_PREFIX}.{handle.name}.{_COLLECTION_LABELS[key]}"


def _validate_category_and_mode(category: str, mode: str) -> None:
    if category not in _CATEGORY_VALUES:
        raise ValueError(f"unsupported light-linking category: {category!r}")
    if mode not in _LINK_STATE_VALUES:
        raise ValueError(f"unsupported light-linking mode: {mode!r}")


def _target_list_property_name(category: str, mode: str) -> str:
    if category == "LIGHT" and mode == "INCLUDE":
        return "light_linking_include_targets"
    if category == "LIGHT" and mode == "EXCLUDE":
        return "light_linking_exclude_targets"
    if category == "SHADOW" and mode == "INCLUDE":
        return "shadow_linking_include_targets"
    return "shadow_linking_exclude_targets"


def _has_property_targets(handle: bpy.types.Object) -> bool:
    props = handle.LLStudio
    return any(
        _target_from_row(row) is not None
        for prop_name, _bucket_key in _PROPERTY_BUCKETS
        for row in getattr(props, prop_name)
    )


def _target_from_row(
    row: bpy.types.PropertyGroup,
) -> bpy.types.Object | bpy.types.Collection | None:
    if row.target_type == "COLLECTION":
        return row.collection_target
    return row.object_target


def _set_row_target(
    row: bpy.types.PropertyGroup,
    target: bpy.types.Object | bpy.types.Collection,
) -> None:
    if isinstance(target, bpy.types.Collection):
        row.target_type = "COLLECTION"
        row.collection_target = target
    else:
        row.target_type = "OBJECT"
        row.object_target = target


def _remove_target_rows(
    rows: bpy.types.bpy_prop_collection,
    target: bpy.types.Object | bpy.types.Collection,
) -> None:
    for index in reversed(range(len(rows))):
        if _target_from_row(rows[index]) == target:
            rows.remove(index)


def _category_buckets(
    collections: dict[str, bpy.types.Collection],
    category: str,
) -> tuple[bpy.types.Collection, bpy.types.Collection]:
    if category == "LIGHT":
        return (collections[LIGHT_INCLUDE_BUCKET], collections[LIGHT_EXCLUDE_BUCKET])
    return (collections[SHADOW_INCLUDE_BUCKET], collections[SHADOW_EXCLUDE_BUCKET])


def _link_target(
    collection: bpy.types.Collection,
    target: bpy.types.Object | bpy.types.Collection,
) -> None:
    if isinstance(target, bpy.types.Collection):
        if collection.children.find(target.name) < 0:
            collection.children.link(target)
    elif collection.objects.find(target.name) < 0:
        collection.objects.link(target)


def _unlink_target(
    collection: bpy.types.Collection,
    target: bpy.types.Object | bpy.types.Collection,
) -> None:
    if isinstance(target, bpy.types.Collection):
        if collection.children.find(target.name) >= 0:
            collection.children.unlink(target)
    elif collection.objects.find(target.name) >= 0:
        collection.objects.unlink(target)


def _bucket_has_targets(collection: bpy.types.Collection) -> bool:
    return bool(collection.objects) or bool(collection.children)


def _build_native_wrapper(
    native_wrapper: bpy.types.Collection,
    include_bucket: bpy.types.Collection,
    exclude_bucket: bpy.types.Collection,
) -> None:
    _unlink_all_direct_targets(native_wrapper)
    for obj in include_bucket.objects:
        _link_target_with_state(native_wrapper, obj, "INCLUDE")
    for collection in include_bucket.children:
        _link_target_with_state(native_wrapper, collection, "INCLUDE")
    for obj in exclude_bucket.objects:
        _link_target_with_state(native_wrapper, obj, "EXCLUDE")
    for collection in exclude_bucket.children:
        _link_target_with_state(native_wrapper, collection, "EXCLUDE")


def _unlink_all_direct_targets(collection: bpy.types.Collection) -> None:
    for obj in list(collection.objects):
        collection.objects.unlink(obj)
    for child in list(collection.children):
        collection.children.unlink(child)


def _link_target_with_state(
    collection: bpy.types.Collection,
    target: bpy.types.Object | bpy.types.Collection,
    link_state: str,
) -> None:
    _link_target(collection, target)
    if isinstance(target, bpy.types.Collection):
        index = collection.children.find(target.name)
        collection.collection_children[index].light_linking.link_state = link_state
    else:
        index = collection.objects.find(target.name)
        collection.collection_objects[index].light_linking.link_state = link_state
