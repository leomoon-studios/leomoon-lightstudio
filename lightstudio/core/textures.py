"""Lazy, mtime-cached scan of the bundled real-light textures folder.

The legacy add-on scanned ``textures_real_lights/`` eagerly at import
time inside ``light_preview_list.py``. That breaks when the package
lives inside a zip and inflates registration cost. This module replaces
that with an on-demand ``scan()`` that caches by directory mtime so
repeated calls are essentially free.
"""

from __future__ import annotations

from pathlib import Path

from .paths import TEXTURES_DIR

_VALID_SUFFIXES: frozenset[str] = frozenset({".exr", ".hdr"})

_cache: tuple[float, tuple[Path, ...]] | None = None


def scan(directory: Path | None = None) -> tuple[Path, ...]:
    """Return a tuple of texture file paths under *directory*.

    The result is sorted by filename and cached by the directory's
    ``mtime``; subsequent calls with no filesystem changes return the
    cached tuple. Pass ``directory`` only in tests; production code
    should use the default ``TEXTURES_DIR``.
    """
    global _cache
    target = directory if directory is not None else TEXTURES_DIR
    if not target.is_dir():
        _cache = None
        return ()
    mtime = target.stat().st_mtime
    if _cache is not None and _cache[0] == mtime and directory is None:
        return _cache[1]
    files = tuple(
        sorted(
            (p for p in target.iterdir() if p.is_file() and p.suffix.lower() in _VALID_SUFFIXES),
            key=lambda p: p.name.lower(),
        )
    )
    if directory is None:
        _cache = (mtime, files)
    return files


def invalidate() -> None:
    """Drop the in-memory cache; the next ``scan()`` call will re-read disk."""
    global _cache
    _cache = None
