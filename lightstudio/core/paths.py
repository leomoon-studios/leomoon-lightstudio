"""Filesystem paths for the LeoMoon LightStudio extension.

All paths are derived from ``Path(__file__).resolve().parent`` so they
work whether the extension is installed from a built zip (under
``bl_ext/<repo>/leomoon_lightstudio/``) or run in-place from a source
checkout. Modules **must** import from here instead of recomputing paths,
so the asset folder can be relocated in one place.
"""

from __future__ import annotations

from pathlib import Path

#: Root of the installed extension package (``.../leomoon_lightstudio/``).
ADDON_DIR: Path = Path(__file__).resolve().parent.parent

#: Bundled asset folder shipped inside the extension zip.
ASSETS_DIR: Path = ADDON_DIR / "assets"

#: Template ``.blend`` containing the ``LLS_*`` collections, light objects,
#: world setup, and the ``LLS_Light`` template appended by the
#: add-light operator.
LLS_BLEND: Path = ASSETS_DIR / "LLS4.blend"

#: Folder of bundled HDR/EXR textures used by the Real Light shader.
TEXTURES_DIR: Path = ASSETS_DIR / "textures_real_lights"
