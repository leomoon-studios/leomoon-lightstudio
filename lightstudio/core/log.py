"""Tiny logging helper for the LeoMoon LightStudio extension.

Centralizes all stdout output so the rest of the package never calls
``print()`` directly. Keeps the prefix consistent and makes it easy to
swap to ``logging`` later without touching call sites.
"""

from __future__ import annotations

_PREFIX = "[LeoMoon LightStudio]"


def log(msg: str) -> None:
    """Print a message to stdout with the extension's prefix."""
    print(f"{_PREFIX} {msg}")


def log_raw(msg: str) -> None:
    """Print a message verbatim (no prefix). For multi-line banners."""
    print(msg)
