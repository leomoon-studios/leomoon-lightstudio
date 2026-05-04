"""Pure-Python tests for ``lightstudio.core.light_data`` and ``core.common``.

Modules are loaded by file path (textcounter pattern) so
``lightstudio/__init__.py`` — which imports ``bpy`` — is never executed.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

PKG_DIR = Path(__file__).resolve().parent.parent / "lightstudio"


def _load(name: str, relpath: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, PKG_DIR / relpath)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


light_data = _load("lightstudio_core_light_data", "core/light_data.py")
common = _load("lightstudio_core_common", "core/common.py")


def test_default_lightdict_matches_schema() -> None:
    ld = light_data.LightDict()
    snapshot = ld.to_dict()
    assert snapshot == light_data.LIGHT_DEFAULTS
    snapshot["radius"] = 999.0
    assert light_data.LightDict()["radius"] == 30.0


def test_lightdict_overrides_merge_on_top_of_defaults() -> None:
    ld = light_data.LightDict({"light_name": "Key", "radius": 12.5})
    assert ld["light_name"] == "Key"
    assert ld["radius"] == 12.5
    assert ld["type"] == "ADVANCED"
    assert ld["basic"]["intensity"] == 2.0


def test_to_json_round_trip_is_lossless() -> None:
    ld = light_data.LightDict({"light_name": "Fill", "rotation": 1.25})
    parsed = light_data.LightDict.from_json(ld.to_json())
    assert parsed == ld
    raw = json.loads(ld.to_json())
    assert raw["light_name"] == "Fill"
    assert raw["rotation"] == 1.25


def test_from_json_rejects_non_object() -> None:
    with pytest.raises(light_data.InvalidLight):
        light_data.LightDict.from_json("[1, 2, 3]")


def test_backfill_basic_from_advanced() -> None:
    ld = light_data.LightDict()
    ld["basic"] = {}
    ld["advanced"]["Color Overlay"] = [0.5, 0.25, 0.125, 1.0]
    ld["advanced"]["Color Saturation"] = 0.7
    ld["advanced"]["Intensity"] = 4.0
    ld.backfill_basic_from_advanced()
    assert ld["basic"]["color"] == [0.5, 0.25, 0.125]
    assert ld["basic"]["color_saturation"] == 0.7
    assert ld["basic"]["intensity"] == 4.0


def test_lls_name_classifiers() -> None:
    assert common.is_lls_name("LEOMOON_LIGHT_STUDIO")
    assert common.is_lls_name("LLS_PROFILE.001")
    assert not common.is_lls_name("Cube")
    assert common.is_lls_root_name("LEOMOON_LIGHT_STUDIO.001")
    assert common.is_light_group_name("LLS_LIGHT.001")
    assert not common.is_light_group_name("LLS_LIGHT_HANDLE")
    assert common.is_profile_group_name("LLS_PROFILE.042")
    assert not common.is_profile_group_name("LLS_PROFILE")
