# Legacy snapshot

This folder is the **pre-extension snapshot** of LeoMoon LightStudio v2.16.3
(the last release built against the legacy `bl_info` add-on format).

It is kept here as a read-only reference while the add-on is rewritten as a
Blender 5 extension under [../lightstudio/](../lightstudio/), following the plan
in [../STEPS.md](../STEPS.md).

## Rules

- **Do not modify** these files. If you find a bug, fix it in the new
  `lightstudio/` package instead.
- This folder is **excluded** from:
  - `ruff` and `mypy` (see [../pyproject.toml](../pyproject.toml)).
  - the built extension `.zip` (see `paths_exclude_pattern` in
    [../lightstudio/blender_manifest.toml](../lightstudio/blender_manifest.toml)).
  - the GitHub Actions release workflow (see
    [../.github/workflows/release.yml](../.github/workflows/release.yml)).
- The original `bl_info` block has been removed from `__init__.py` because
  Blender 5 forbids it; the file is otherwise byte-identical to the v2.16.3
  release.
- `git log --follow legacy/<file>` still works — history was preserved with
  `git mv`.

## Removal

This folder will be deleted in the final task of step 20 in
[../STEPS.md](../STEPS.md), once the new extension reaches feature parity and
is verified to install and run cleanly in a fresh Blender 5.x profile.
