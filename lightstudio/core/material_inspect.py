"""Material introspection helpers for LeoMoon LightStudio.

Two layers:

- :func:`group_inputs_by_color` — pure (no ``bpy``) helper that takes a
  list of ``(name, type, default)`` tuples (the way the GUI consumes
  shader-group sockets) and returns a list of column groups: every
  ``RGBA`` input begins a new column. The legacy GUI hand-rolled this
  inside ``gui.py``; tests can pin the behaviour without a Blender
  process.
- :func:`get_advanced_inputs` — bpy-coupled wrapper that, given an
  active mesh-light material, returns the same ``(name, type, default)``
  tuples by walking ``node_tree.nodes["Group"].inputs[2:]`` (skipping
  the first two internal sockets the way the legacy panel did).
"""

from __future__ import annotations

from typing import Any


def group_inputs_by_color(
    inputs: list[tuple[str, str, Any]],
) -> list[list[tuple[str, str, Any]]]:
    """Split ``inputs`` into column groups; every ``RGBA`` socket starts one.

    The legacy panel rendered every ``RGBA`` socket on its own row and
    appended subsequent non-RGBA sockets to a column underneath it. The
    returned structure mirrors that: the first group runs from the
    start (or the previous RGBA) up to (but not including) the next
    RGBA. Empty groups are not emitted.
    """
    groups: list[list[tuple[str, str, Any]]] = []
    current: list[tuple[str, str, Any]] = []
    for entry in inputs:
        _name, kind, _default = entry
        if kind == "RGBA":
            if current:
                groups.append(current)
            current = [entry]
        else:
            current.append(entry)
    if current:
        groups.append(current)
    return groups


def get_advanced_inputs(material) -> list[tuple[str, str, object]]:
    """Return ``[(name, type, default_value), ...]`` for the LLS shader group.

    Skips the first two sockets (legacy convention — they hold internal
    wiring that the GUI never exposes). Returns an empty list if the
    material does not contain a ``Group`` node.
    """
    try:
        group = material.node_tree.nodes["Group"]
    except (AttributeError, KeyError):
        return []
    return [(s.name, s.type, s.default_value) for s in group.inputs[2:]]
