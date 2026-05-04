"""Pure helpers shared across the LeoMoon LightStudio extension.

The legacy ``common.py`` is overwhelmingly ``bpy``-coupled (every helper
walks Blender object trees) and is ported alongside the operators that
need it in steps 10-12. What lives here is the thin **naming convention**
layer that *is* pure: the LLS object-name prefixes and the small
classifier built on top of them. Keeping this here means tests for
profile/light bookkeeping can run without a Blender process.
"""

from __future__ import annotations

#: Prefix attached to the root empty of an LLS scene.
ROOT_PREFIX: str = "LEOMOON_LIGHT_STUDIO"

#: Prefix shared by every LLS-managed object inside a profile.
LLS_PREFIX: str = "LLS_"

#: Specific LLS object-name prefixes used to locate the parts of a light.
LIGHT_GROUP_PREFIX: str = "LLS_LIGHT."
LIGHT_HANDLE_PREFIX: str = "LLS_LIGHT_HANDLE"
LIGHT_MESH_PREFIX: str = "LLS_LIGHT_MESH"
LIGHT_AREA_PREFIX: str = "LLS_LIGHT_AREA"
PROFILE_PREFIX: str = "LLS_PROFILE"
PROFILE_GROUP_PREFIX: str = "LLS_PROFILE."
HANDLE_PREFIX: str = "LLS_HANDLE"
ROTATION_PREFIX: str = "LLS_ROTATION"


def is_lls_name(name: str) -> bool:
    """Return ``True`` if *name* belongs to the LLS family of objects."""
    return name == ROOT_PREFIX or name.startswith(LLS_PREFIX) or name.startswith(ROOT_PREFIX)


def is_lls_root_name(name: str) -> bool:
    """Return ``True`` if *name* is the LLS scene root empty."""
    return name == ROOT_PREFIX or name.startswith(ROOT_PREFIX)


def is_light_group_name(name: str) -> bool:
    """Return ``True`` for the ``LLS_LIGHT.<n>`` per-light group empty."""
    return name.startswith(LIGHT_GROUP_PREFIX)


def is_profile_group_name(name: str) -> bool:
    """Return ``True`` for the ``LLS_PROFILE.<n>`` per-profile group empty."""
    return name.startswith(PROFILE_GROUP_PREFIX)
