"""Hotkeys reference panel — static help labels."""

from __future__ import annotations

import bpy

from .._common import PANEL_CATEGORY, PANEL_REGION, PANEL_SPACE, studio_initialized


class LLS_PT_Hotkeys(bpy.types.Panel):
    bl_idname = "LLS_PT_hotkeys"
    bl_label = "Hotkeys"
    bl_space_type = PANEL_SPACE
    bl_region_type = PANEL_REGION
    bl_category = PANEL_CATEGORY

    # Defaults until step 16 wires the keymap reader that updates these.
    move_kmi_type = "EVENT_G"
    scale_kmi_type = "EVENT_S"
    rotate_kmi_type = "EVENT_R"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return studio_initialized(context)

    def draw(self, context: bpy.types.Context) -> None:
        box = self.layout.box()
        box.label(text="Move light", icon=self.__class__.move_kmi_type)
        box.label(text="Scale light", icon=self.__class__.scale_kmi_type)
        box.label(text="Rotate light", icon=self.__class__.rotate_kmi_type)
        box.label(text="Precision mode", icon="EVENT_SHIFT")
        box.label(text="Mute light", icon="MOUSE_LMB_DRAG")
        box.label(text="Isolate light", icon="MOUSE_RMB")
        row = box.row(align=True)
        row.alignment = "LEFT"
        row.label(text="", icon="EVENT_CTRL")
        row.label(text=" ")
        row.label(text="", icon="MOUSE_LMB")
        row.label(text="Cycle overlapping lights")
        box.label(text="(numpad) Icon scale up", icon="ADD")
        box.label(text="(numpad) Icon scale down", icon="REMOVE")


classes: tuple[type[bpy.types.Panel], ...] = (LLS_PT_Hotkeys,)
