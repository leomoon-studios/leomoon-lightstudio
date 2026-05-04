"""Pytest configuration for the LeoMoon LightStudio test suite.

Tests under ``tests/headless/`` import ``bpy`` and must run inside a
Blender process (via ``make headless-test``); the plain ``pytest`` run
used by ``make test`` and CI cannot import them, so they are skipped at
collection time. Step 19 expands this into an env-var-aware conftest
(``BLENDER`` set ⇒ collect them too).
"""

from __future__ import annotations

collect_ignore_glob: list[str] = ["headless/*"]
