"""App handlers, msgbus, keymaps, and keying-set registration.

Step 16 lands the central keymap registry. Step 17 adds the persistent
app handlers (frame_change_post light energy sync, render_complete /
render_cancel EXR cleanup), the LayerObjects.active msgbus subscription
for ANIMATION-mode handle reveal, and the
``BUILTIN_KSI_LightStudio`` keying set + activation operator.
"""

from . import app_handlers, keying_set, keymaps, msgbus


def register() -> None:
    keying_set.register()
    app_handlers.register()
    msgbus.register()
    keymaps.register()


def unregister() -> None:
    keymaps.unregister()
    msgbus.unregister()
    app_handlers.unregister()
    keying_set.unregister()
