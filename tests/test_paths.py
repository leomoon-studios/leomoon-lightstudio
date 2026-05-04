"""Verify bundled-asset paths and the textures cache.

Modules are loaded by file path (textcounter pattern) so ``lightstudio/__init__.py``
— which imports ``bpy`` for register/unregister — is never executed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

PKG_DIR = Path(__file__).resolve().parent.parent / "lightstudio"


def _load(name: str, relpath: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, PKG_DIR / relpath)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# ``textures`` does ``from .paths import TEXTURES_DIR``. Register a synthetic
# parent package so the relative import resolves, then load both modules under
# fully-qualified names.
_pkg_name = "_lightstudio_core_under_test"
_pkg = ModuleType(_pkg_name)
_pkg.__path__ = [str(PKG_DIR / "core")]
sys.modules[_pkg_name] = _pkg

paths = _load(f"{_pkg_name}.paths", "core/paths.py")
textures = _load(f"{_pkg_name}.textures", "core/textures.py")


def test_paths_resolve_to_bundled_assets() -> None:
    assert paths.ASSETS_DIR.is_dir(), paths.ASSETS_DIR
    assert paths.LLS_BLEND.is_file(), paths.LLS_BLEND
    assert paths.TEXTURES_DIR.is_dir(), paths.TEXTURES_DIR


def test_textures_folder_contains_15_files() -> None:
    files = sorted(p.name for p in paths.TEXTURES_DIR.iterdir() if p.is_file())
    assert len(files) == 15, files


def test_textures_scan_default_returns_15() -> None:
    textures.invalidate()
    assert len(textures.scan()) == 15


def test_textures_scan_filters_and_sorts(tmp_path: Path) -> None:
    (tmp_path / "b.exr").write_bytes(b"")
    (tmp_path / "a.hdr").write_bytes(b"")
    (tmp_path / "ignored.txt").write_bytes(b"")
    result = textures.scan(tmp_path)
    assert [p.name for p in result] == ["a.hdr", "b.exr"]
