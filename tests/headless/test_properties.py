"""Headless smoke test: extension registration installs the LLStudio properties.

Runs **inside Blender** (``blender --background --factory-startup --python ...``).
Uses :mod:`addon_utils` to enable / disable the locally-installed
``leomoon_lightstudio`` extension and asserts the three pointer
properties + ``Object.protected`` flag appear / disappear together.

Invoke with::

    BLENDER=/path/to/blender pytest does *not* run this file
    (see tests/conftest.py once it exists in step 19).

For now run directly::

    blender --background --factory-startup \\
        --python tests/headless/test_properties.py
"""

from __future__ import annotations

import sys

import addon_utils
import bpy

EXTENSION_MODULE = "bl_ext.user_default.leomoon_lightstudio"


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    # 1. Disable first in case a previous run left it enabled, then enable.
    addon_utils.disable(EXTENSION_MODULE, default_set=False)
    module = addon_utils.enable(EXTENSION_MODULE, default_set=False)
    if module is None:
        _fail(f"could not enable {EXTENSION_MODULE}")

    # 2. Pointer properties must exist on the right ID types.
    if not hasattr(bpy.types.Scene, "LLStudio"):
        _fail("Scene.LLStudio not registered")
    if not hasattr(bpy.types.Object, "LLStudio"):
        _fail("Object.LLStudio not registered")
    if not hasattr(bpy.types.Light, "LLStudio"):
        _fail("Light.LLStudio not registered")
    if not hasattr(bpy.types.Object, "protected"):
        _fail("Object.protected not registered")

    # 3. Pointer access on a real datablock returns a populated PropertyGroup.
    scene = bpy.context.scene
    props = scene.LLStudio
    expected = "LeoMoon_Light_Studio_Properties"
    if type(props).__name__ != expected:
        _fail(f"Scene.LLStudio is {type(props).__name__!r}, expected {expected!r}")
    if props.lls_mode != "NORMAL":
        _fail(f"default lls_mode is {props.lls_mode!r}, expected 'NORMAL'")
    if len(props.profile_list) != 0:
        _fail(f"profile_list should start empty, got {len(props.profile_list)} entries")

    # 4. Disable and confirm the pointers + flag are gone (clean teardown).
    addon_utils.disable(EXTENSION_MODULE, default_set=False)
    if hasattr(bpy.types.Scene, "LLStudio"):
        _fail("Scene.LLStudio still present after disable")
    if hasattr(bpy.types.Object, "LLStudio"):
        _fail("Object.LLStudio still present after disable")
    if hasattr(bpy.types.Light, "LLStudio"):
        _fail("Light.LLStudio still present after disable")
    if hasattr(bpy.types.Object, "protected"):
        _fail("Object.protected still present after disable")

    print("PASS: properties register and unregister cleanly")


if __name__ == "__main__":
    main()
