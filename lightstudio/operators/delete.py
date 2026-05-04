"""Custom delete operator for LLS-protected objects (Step 16).

Ports legacy ``deleteOperator.py``:

* ``LLS_OT_DeleteCustom`` — intercepts ``object.delete`` for objects
  flagged with ``Object.protected`` so deleting an LLS light routes
  through ``scene.delete_leomoon_studio_light`` (which cleans up the
  whole light family) instead of orphaning members.

The Del keymap entries are registered centrally by
:mod:`lightstudio.handlers.keymaps`.
"""

from __future__ import annotations

import traceback

import bpy
from bpy.props import BoolProperty

from ..core.scene_utils import is_family, update_light_list_set
from .light import _delete_studio_light


class LLS_OT_DeleteCustom(bpy.types.Operator):
    """Custom delete that routes LLS-protected objects through the LLS cleanup."""

    bl_idname = "object.delete_custom"
    bl_label = "Custom Delete"
    bl_options = {"REGISTER", "UNDO"}

    use_global: BoolProperty(default=False, name="Delete Globally")  # type: ignore[valid-type]
    confirm: BoolProperty(default=True, name="Confirm")  # type: ignore[valid-type]

    @classmethod
    def poll(cls, context):
        if not context.area:
            return True
        return (
            context.area.type == "VIEW_3D"
            and context.mode == "OBJECT"
            and any(
                getattr(ob, "protected", False) for ob in context.selected_objects
            )
        )

    def execute(self, context):
        try:
            for obj in [
                ob for ob in context.selected_objects if getattr(ob, "protected", False)
            ]:
                if obj and obj.name.startswith("LLS_HANDLE"):
                    self.report({"ERROR"}, "Delete Profile in order to delete Handle")
                    return {"FINISHED"}
                if hasattr(obj, "use_fake_user"):
                    obj.use_fake_user = False
                try:
                    _delete_studio_light(context, obj)
                except Exception:  # noqa: BLE001
                    traceback.print_exc()
                    self.report({"ERROR"}, "Error while deleting light")
                    return {"FINISHED"}
        except ReferenceError:
            return {"FINISHED"}

        bpy.ops.object.delete(
            "INVOKE_DEFAULT", use_global=self.use_global, confirm=False
        )

        if context.scene.LLStudio.initialized:
            update_light_list_set(context)
        return {"FINISHED"}

    def invoke(self, context, event):
        from .modal.control_panel import running_modals

        if self.confirm:
            if not running_modals:
                return context.window_manager.invoke_confirm(self, event)
            if running_modals and not is_family(context.object):
                return context.window_manager.invoke_confirm(self, event)
        return self.execute(context)


classes: tuple[type[bpy.types.Operator], ...] = (LLS_OT_DeleteCustom,)
