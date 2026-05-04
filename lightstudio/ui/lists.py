"""``UIList`` widgets for the Profile and Light side panels.

Both ports keep the legacy draw logic intact: every cell falls back to a
``light_studio.refresh_lightlist`` button when the underlying datablocks
are missing (the typical post-scene-duplication state).
"""

from __future__ import annotations

import bpy

from ..core.scene_utils import find_view_layer, get_collection


class LLS_UL_ProfileList(bpy.types.UIList):
    bl_idname = "LLS_UL_ProfileList"

    def draw_item(
        self,
        context: bpy.types.Context,
        layout: bpy.types.UILayout,
        data,
        item,
        icon: int,
        active_data,
        active_propname: str,
        index: int,
    ) -> None:
        props = context.scene.LLStudio
        custom_icon = "OUTLINER_OB_LIGHT" if item.enabled else "LIGHT"

        # Detect "needs refresh" state (matches legacy heuristic).
        if not data.profile_multimode:
            valid = (
                data.profile_list[data.profile_list_index].empty_name
                in context.scene.objects
            )
        else:
            target = data.profile_list[index].empty_name
            occurrences = sum(
                1
                for scene in bpy.data.scenes
                for p in scene.LLStudio.profile_list
                if p.empty_name == target
            )
            valid = occurrences == 1

        if not valid:
            layout.operator("light_studio.refresh_lightlist", text="Refresh...")
            return

        if self.layout_type in {"DEFAULT", "COMPACT"}:
            layout.prop(item, "name", text="", emboss=False, translate=False)
            if props.profile_multimode:
                layout.prop(
                    item,
                    "enabled",
                    text="",
                    emboss=False,
                    translate=False,
                    icon=custom_icon,
                )
                enabled_count = sum(p.enabled for p in props.profile_list)
                solo_icon = (
                    "SOLO_ON" if enabled_count == 1 and item.enabled else "SOLO_OFF"
                )
                layout.operator(
                    "lls_list.isolate_profile", emboss=False, icon=solo_icon, text=""
                ).index = index
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text="", icon=custom_icon)


class LLS_UL_LightList(bpy.types.UIList):
    bl_idname = "LLS_UL_LightList"

    def draw_item(
        self,
        context: bpy.types.Context,
        layout: bpy.types.UILayout,
        data,
        item,
        icon: int,
        active_data,
        active_propname: str,
        index: int,
    ) -> None:
        if item.handle_name not in context.scene.objects:
            layout.operator("light_studio.refresh_lightlist", text="Refresh...")
            return

        if self.layout_type in {"DEFAULT", "COMPACT"}:
            layout.prop(item, "name", text="", emboss=False, translate=False)

            mesh_object = context.scene.objects[item.handle_name]
            mesh_collection = get_collection(mesh_object)
            view_layer = find_view_layer(
                mesh_collection, context.view_layer.layer_collection
            )
            mute_excluded = bool(view_layer and view_layer.exclude)
            mute_icon = "LIGHT" if mute_excluded else "OUTLINER_OB_LIGHT"

            sub = layout.row(align=True)
            sub.operator(
                "light_studio.mute_toggle", emboss=False, icon=mute_icon, text=""
            ).index = index

            props = context.scene.LLStudio
            excluded = 0
            for li in props.light_list:
                if li.handle_name not in context.scene.objects:
                    continue
                obj = context.scene.objects[li.handle_name]
                vl = find_view_layer(
                    get_collection(obj), context.view_layer.layer_collection
                )
                if vl and vl.exclude:
                    excluded += 1

            solo_icon = (
                "SOLO_ON"
                if excluded == len(props.light_list) - 1 and not mute_excluded
                else "SOLO_OFF"
            )
            sub.operator(
                "light_studio.isolate", emboss=False, icon=solo_icon, text=""
            ).index = index
            sub.prop(item, "visible_camera", text="", icon="VIEW_CAMERA")
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text="", icon="OUTLINER_OB_LIGHT")


classes: tuple[type[bpy.types.UIList], ...] = (
    LLS_UL_ProfileList,
    LLS_UL_LightList,
)
