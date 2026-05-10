"""Light data schema and JSON serialization.

This is the **pure-Python** half of the legacy ``light_data.py``: the
canonical ``LightDict`` schema (defaults for every key the legacy
profile files persist) and JSON round-trip helpers used by the
import/export operators in step 12. The Blender-side code that walks
material nodes and reads scene state stays in
``lightstudio/operators/profiles.py`` (ported in step 12) and consumes
this module purely as a data layer.

Importing this module never touches ``bpy`` so it can be unit-tested
under plain ``pytest`` without a Blender process.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from typing import Any

LightType = str  # "ADVANCED" | "BASIC"


class InvalidLight(Exception):
    """Raised when a profile entry cannot be parsed into a valid light."""


#: Default value for every key persisted in a light dictionary. Mirrors the
#: legacy ``LightDict._dict`` so exported profiles stay backward compatible.
LIGHT_DEFAULTS: dict[str, Any] = {
    "advanced": {
        "tex": "Soft Box A.exr",
        "Texture Switch": 1.0,
        "Color Overlay": [1.0, 0.4000000059604645, 0.15000000596046448, 1.0],
        "Color Saturation": 0.0,
        "Intensity": 2.0,
        "Exposure": 1.0,
        "Mask - Gradient Switch": 0.0,
        "Mask - Gradient Type": 0.0,
        "Mask - Gradient Amount": 0.0,
        "Mask - Ring Switch": 0.0,
        "Mask - Ring Inner Radius": 0.0,
        "Mask - Ring Outer Radius": 0.0,
        "Mask - Top to Bottom": 0.0,
        "Mask - Bottom to Top": 0.0,
        "Mask - Left to Right": 0.0,
        "Mask - Right to Left": 0.0,
        "Mask - Diagonal Top Left": 0.0,
        "Mask - Diagonal Top Right": 0.0,
        "Mask - Diagonal Bottom Right": 0.0,
        "Mask - Diagonal Bottom Left": 0.0,
        "Mask - Backface": 0.0,
    },
    "basic": {
        "color": [1.0, 1.0, 1.0],
        "color_saturation": 0.0,
        "intensity": 2.0,
    },
    "light_name": "",
    "order_index": 0,
    "radius": 30.0,
    "position": [0.0, 0.0],
    "rotation": 0.0,
    "scale": [1.0, 1.0, 1.0],
    "type": "ADVANCED",
    "visible_camera": True,
    "mute": False,
}


class LightDict:
    """Mutable dict-like container for a single light's serialized state.

    Construction from ``None`` produces a deep copy of ``LIGHT_DEFAULTS``;
    passing an existing mapping shallow-merges it on top of the defaults
    (matching the legacy behavior). Use ``to_json`` / ``from_json`` for
    on-disk persistence and ``backfill_basic_from_advanced`` to repair
    older profiles that pre-date the basic-light fields.
    """

    __slots__ = ("dict",)

    def __init__(self, real_dict: Mapping[str, Any] | None = None) -> None:
        self.dict: dict[str, Any] = copy.deepcopy(LIGHT_DEFAULTS)
        if real_dict:
            self.dict.update(real_dict)

    def __getitem__(self, key: str) -> Any:
        return self.dict[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.dict[key] = value

    def __contains__(self, key: object) -> bool:
        return key in self.dict

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LightDict):
            return self.dict == other.dict
        if isinstance(other, Mapping):
            return self.dict == dict(other)
        return NotImplemented

    def __repr__(self) -> str:
        return f"LightDict({self.dict!r})"

    def __str__(self) -> str:
        return json.dumps(self.dict, indent=4, separators=(",", ": "))

    def to_dict(self) -> dict[str, Any]:
        """Return a deep copy of the underlying dict."""
        return copy.deepcopy(self.dict)

    def to_json(self, *, indent: int = 4) -> str:
        """Serialize to a JSON string (matches the legacy export format)."""
        return json.dumps(self.dict, indent=indent, separators=(",", ": "))

    @classmethod
    def from_json(cls, payload: str) -> LightDict:
        """Parse a JSON string back into a ``LightDict``."""
        data = json.loads(payload)
        if not isinstance(data, Mapping):
            raise InvalidLight(f"expected a JSON object, got {type(data).__name__}")
        return cls(data)

    def backfill_basic_from_advanced(self) -> None:
        """Populate ``basic`` fields from ``advanced`` for pre-basic profiles.

        Older exports (before the basic-light type existed) only stored
        the advanced shader inputs. This mirrors the legacy
        ``light_from_dict`` behavior of synthesising the basic-light
        color/saturation/intensity from ``Color Overlay`` etc.
        """
        adv = self.dict.get("advanced", {})
        basic = self.dict.setdefault("basic", {})
        if "Color Overlay" in adv and len(adv["Color Overlay"]) >= 3:
            basic["color"] = list(adv["Color Overlay"][:3])
        if "Color Saturation" in adv:
            basic["color_saturation"] = adv["Color Saturation"]
        if "Intensity" in adv:
            basic["intensity"] = adv["Intensity"]
