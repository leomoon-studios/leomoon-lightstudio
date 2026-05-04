"""Pure-Python helpers for LeoMoon LightStudio.

This subpackage holds code that does **not** touch ``bpy`` at import time
(paths, logging, serialization, material introspection helpers, etc.) so
it can be unit-tested under plain ``pytest`` without a Blender process.

Registration policy
-------------------
The legacy add-on used ``auto_load.py`` to walk the package tree and
register every ``bpy.types.*`` subclass it found. The extension rewrite
drops that approach in favor of **explicit registration lists per
subpackage**: each subpackage exposes its own ``register()`` /
``unregister()`` and the top-level ``lightstudio/__init__.py`` calls them
in dependency order (``properties → operators → ui → handlers``). This
keeps load order deterministic, plays nicely with the namespaced
``bl_ext.<repo>.leomoon_lightstudio`` import path, and avoids the lazy
``__path__`` traversal that historically caused issues when the package
lives inside a zip.

If a future module ever needs auto-discovery, port ``legacy/auto_load.py``
into this folder and update its module walk to use ``__package__`` instead
of ``__name__``.
"""
