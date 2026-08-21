"""``UIList`` widgets for the Profile and Light side panels.

Both ports keep the legacy draw logic intact: every cell falls back to a
``light_studio.refresh_lightlist`` button when the underlying datablocks
are missing (the typical post-scene-duplication state).
"""

from __future__ import annotations

import bpy

from ..core.scene_utils import find_view_layer, get_collection


def _row_has_target(row: bpy.types.PropertyGroup) -> bool:
    if row.target_type == "COLLECTION":
        return row.collection_target is not None
    return row.object_target is not None


def _handle_has_targets(
    handle: bpy.types.Object,
    prop_names: tuple[str, str],
) -> bool:
    props = getattr(handle, "LLStudio", None)
    return bool(
        props
        and any(
            _row_has_target(row)
            for prop_name in prop_names
            for row in getattr(props, prop_name, ())
        )
    )


class LLS_OT_LinkBadge(bpy.types.Operator):
    bl_idname = "light_studio.link_badge"
    bl_label = "Light Linking"
    bl_options = {"INTERNAL"}

    has_light_links: bpy.props.BoolProperty(default=False)
    has_shadow_links: bpy.props.BoolProperty(default=False)

    @classmethod
    def description(cls, context: bpy.types.Context, properties) -> str:
        lines = []
        if properties.has_light_links:
            lines.append("This light has Light Linking targets")
        if properties.has_shadow_links:
            lines.append("This light has Shadow Linking targets")
        return "\n".join(lines) if lines else "This light has no linking targets"

    def execute(self, context: bpy.types.Context) -> set[str]:
        return {"FINISHED"}


class LLS_OT_LinkDivider(bpy.types.Operator):
    bl_idname = "light_studio.link_divider"
    bl_label = ""
    bl_description = "Devider."
    bl_options = {"INTERNAL"}

    @classmethod
    def description(cls, context: bpy.types.Context, properties) -> str:
        return ""

    def execute(self, context: bpy.types.Context) -> set[str]:
        return {"FINISHED"}


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
            has_light_links = _handle_has_targets(
                mesh_object,
                ("light_linking_include_targets", "light_linking_exclude_targets"),
            )
            has_shadow_links = _handle_has_targets(
                mesh_object,
                ("shadow_linking_include_targets", "shadow_linking_exclude_targets"),
            )
            if has_light_links or has_shadow_links:
                badge = sub.operator(
                    "light_studio.link_badge",
                    emboss=False,
                    icon="LINKED",
                    text="",
                )
                badge.has_light_links = has_light_links
                badge.has_shadow_links = has_shadow_links
                # sub.separator(factor=2)
                sub.operator(
                    "light_studio.link_divider",
                    emboss=False,
                    icon="GRIP_V",
                    text="",
                )
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
            pinned = props.pin_selected_light and props.pinned_light_handle_name == item.handle_name
            pin_icon = "PINNED" if pinned else "UNPINNED"
            sub.operator(
                "light_studio.pin_light",
                emboss=False,
                icon=pin_icon,
                text="",
                depress=pinned,
            ).index = index
            camera_icon = "VIEW_CAMERA" if item.visible_camera else "VIEW_CAMERA_UNSELECTED"
            sub.operator(
                "light_studio.camera_toggle",
                emboss=False,
                icon=camera_icon,
                text="",
            ).index = index
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text="", icon="OUTLINER_OB_LIGHT")


classes: tuple[type[bpy.types.Operator] | type[bpy.types.UIList], ...] = (
    LLS_OT_LinkBadge,
    LLS_OT_LinkDivider,
    LLS_UL_ProfileList,
    LLS_UL_LightList,
)
