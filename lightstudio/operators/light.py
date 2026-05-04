"""Light add / delete / copy / move / mute / isolate / camera-toggle operators.

Ported from legacy ``light_operators.AddLLSLight`` /
``DeleteBSLight`` / ``LLS_OT_camera_toggle_all_lights`` and from
``light_list.{LLS_OT_MuteToggle, LLS_OT_Isolate,
LLS_OT_LightListMoveItem, LIST_OT_LightListCopyItem}``.

Notes versus legacy:

- Append source is :data:`lightstudio.core.paths.LLS_BLEND` instead of a
  computed-relative path.
- Modal-panel hooks (``send_light_to_top``, ``update_light_sets``) are
  imported behind ``try / except ImportError`` so they activate
  automatically once step 15 lands.
- ``check_profiles_consistency`` (step 12) is a no-op for now; the
  hierarchy walks below tolerate the simpler "single-profile, no
  multimode" world this step ships.
"""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty

from ..core.log import log
from ..core.paths import LLS_BLEND
from ..core.scene_utils import (
    duplicate_collection,
    family,
    find_light_grp,
    find_light_profile_object,
    find_view_layer,
    get_collection,
    get_lls_collection,
    llscol_profilecol,
    llscol_profilecol_profile_handle,
    update_light_list_set,
)


class LLS_OT_AddLight(bpy.types.Operator):
    bl_idname = "scene.add_leomoon_studio_light"
    bl_label = "Add Studio Light"
    bl_description = "Add a new light to studio"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        props = context.scene.LLStudio
        if not props.initialized:
            return False
        if not len(props.profile_list):
            return False
        if props.profile_multimode:
            return props.profile_list[props.profile_list_index].enabled
        return True

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            _lls, profile_collection, _profile_empty, handle = (
                llscol_profilecol_profile_handle(context)
            )
        except (KeyError, StopIteration) as exc:
            self.report({"ERROR"}, f"LLS hierarchy incomplete: {exc}")
            return {"CANCELLED"}

        with bpy.data.libraries.load(str(LLS_BLEND)) as (data_from, data_to):
            data_to.collections = ["LLS_Light"]

        light_collection = data_to.collections[0]
        if light_collection is None:
            self.report({"ERROR"}, "LLS_Light template not found in LLS4.blend")
            return {"CANCELLED"}

        profile_collection.children.link(light_collection)

        advanced_col = next(
            c for c in light_collection.children if c.name.startswith("LLS_Advanced")
        )
        basic_col = next(
            c for c in light_collection.children if c.name.startswith("LLS_Basic")
        )
        new_objects = (
            list(light_collection.objects)
            + list(advanced_col.objects)
            + list(basic_col.objects)
        )
        for ob in new_objects:
            ob.use_fake_user = True

        light_group = next(
            ob for ob in new_objects if ob.name.startswith("LLS_LIGHT.")
        )
        # Find profile object (LLS_PROFILE.*) for parenting.
        profile_obj = next(
            ob for ob in profile_collection.objects if ob.name.startswith("LLS_PROFILE")
        )
        light_group.parent = profile_obj

        bpy.ops.object.select_all(action="DESELECT")

        light_handle = next(
            ob for ob in new_objects if ob.name.startswith("LLS_LIGHT_HANDLE")
        )
        light_handle.LLStudio.order_index = len(context.scene.LLStudio.light_list)

        # Pick light type from the active engine. Setting the enum may be
        # a no-op (default == "ADVANCED"), so toggle the layer-collection
        # exclude flags directly to guarantee initial visibility.
        from ..core.scene_utils import find_view_layer

        if context.scene.render.engine in {"BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"}:
            light_handle.LLStudio.type = "BASIC"
            active_col, hidden_col = basic_col, advanced_col
        else:
            light_handle.LLStudio.type = "ADVANCED"
            active_col, hidden_col = advanced_col, basic_col

        active_view = find_view_layer(
            active_col, context.view_layer.layer_collection
        )
        hidden_view = find_view_layer(
            hidden_col, context.view_layer.layer_collection
        )
        if active_view is not None:
            active_view.exclude = False
        if hidden_view is not None:
            hidden_view.exclude = True

        light_object = active_col.objects[0]
        context.view_layer.objects.active = light_object
        light_object.select_set(True)

        constraint = light_handle.constraints.new("CHILD_OF")
        constraint.target = handle
        constraint.inverse_matrix.identity()

        update_light_list_set(context)
        log("light added")
        return {"FINISHED"}


def _delete_studio_light(context: bpy.types.Context, obj: bpy.types.Object) -> None:
    light_group = find_light_grp(obj)
    if light_group is None:
        return
    light_collection = light_group.users_collection[0] if light_group.users_collection else None
    if light_collection is None or not light_collection.name.startswith("LLS_Light"):
        return
    cols_to_remove = [light_collection, *light_collection.children[:]]
    for ob in family(light_group):
        bpy.data.objects.remove(ob)
    for col in cols_to_remove:
        bpy.data.collections.remove(col)
    update_light_list_set(context)


class LLS_OT_DeleteLight(bpy.types.Operator):
    bl_idname = "scene.delete_leomoon_studio_light"
    bl_label = "Delete Studio Light"
    bl_description = "Delete selected light from studio"
    bl_options = {"REGISTER", "UNDO"}

    confirm: BoolProperty(default=True)

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        if not context.area:
            return True
        props = context.scene.LLStudio
        if not (
            context.area.type == "VIEW_3D"
            and context.mode == "OBJECT"
            and props.initialized
        ):
            return False
        light = context.active_object
        if not (
            (light and light.name.startswith("LLS_LIGHT"))
            or (context.object and context.object.name.startswith("LLS_LIGHT"))
        ):
            return False
        if props.profile_multimode:
            if props.profile_list_index >= len(props.profile_list):
                return False
            return props.profile_list[props.profile_list_index].enabled
        return True

    def execute(self, context: bpy.types.Context) -> set[str]:
        if context.object is None:
            return {"CANCELLED"}
        _delete_studio_light(context, context.object)
        log("light deleted")
        return {"FINISHED"}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        if self.confirm:
            return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)

    def draw(self, context: bpy.types.Context) -> None:
        self.layout.column(align=True).label(text="OK?")


class LLS_OT_MuteToggle(bpy.types.Operator):
    bl_idname = "light_studio.mute_toggle"
    bl_label = "Mute Light"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    index: IntProperty(default=-1)

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return (
            context.area is not None
            and context.area.type == "VIEW_3D"
            and context.mode == "OBJECT"
            and context.scene.LLStudio.initialized
        )

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = context.scene.LLStudio
        if self.index < 0 or self.index >= len(props.light_list):
            return {"CANCELLED"}
        item = props.light_list[self.index]
        item.mute = not item.mute
        return {"FINISHED"}


class LLS_OT_Isolate(bpy.types.Operator):
    bl_idname = "light_studio.isolate"
    bl_label = "Isolate Light"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    index: IntProperty(default=-1)

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return (
            context.area is not None
            and context.area.type == "VIEW_3D"
            and context.mode == "OBJECT"
            and context.scene.LLStudio.initialized
        )

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = context.scene.LLStudio
        if self.index < 0 or self.index >= len(props.light_list):
            return {"CANCELLED"}
        target = props.light_list[self.index]
        included = sum(1 for li in props.light_list if not li.mute)
        if not target.mute and included == 1:
            # Restore previously-stored mute state for everyone.
            for li in props.light_list:
                li.mute = li.exclude_isolate > 0 if li.exclude_isolate > -1 else False
                li.exclude_isolate = -1
        else:
            for li in props.light_list:
                if li.exclude_isolate == -1:
                    li.exclude_isolate = 1 if li.mute else 0
                if not li.mute:
                    li.mute = True
            target.mute = False
        return {"FINISHED"}


class LLS_OT_LightListMove(bpy.types.Operator):
    bl_idname = "lls_list.move_light"
    bl_label = "Move Light"
    bl_options = {"INTERNAL"}

    direction: EnumProperty(
        items=(
            ("UP", "Up", ""),
            ("DOWN", "Down", ""),
        ),
    )

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return bool(len(context.scene.LLStudio.light_list))

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = context.scene.LLStudio
        lst = props.light_list
        index = props.light_list_index
        if self.direction == "DOWN":
            if index + 1 >= len(lst):
                return {"CANCELLED"}
            lst.move(index, index + 1)
        elif self.direction == "UP":
            if index <= 0:
                return {"CANCELLED"}
            lst.move(index - 1, index)
        else:
            return {"CANCELLED"}

        for i, e in enumerate(lst):
            handle = bpy.data.objects.get(e.handle_name)
            if handle is not None:
                handle.LLStudio.order_index = i
        return {"FINISHED"}


class LLS_OT_LightListCopy(bpy.types.Operator):
    bl_idname = "lls_list.copy_light"
    bl_label = "Copy Light"
    bl_description = "Duplicate the active LLS light"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        if context.area is None or context.area.type != "VIEW_3D":
            return False
        if context.mode != "OBJECT":
            return False
        props = context.scene.LLStudio
        if not props.initialized:
            return False
        light = context.active_object
        if not (light and light.name.startswith("LLS_LIGHT_")):
            return False
        if props.profile_multimode:
            profile = find_light_profile_object(light)
            if props.profile_list_index >= len(props.profile_list):
                return False
            list_profile = props.profile_list[props.profile_list_index]
            return bool(list_profile.enabled and profile and profile.name == list_profile.empty_name)
        return True

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = context.scene.LLStudio
        _lls, profile_collection = llscol_profilecol(context)
        if profile_collection is None:
            return {"CANCELLED"}
        lls_handle = context.object.parent if context.object else None
        if lls_handle is None:
            return {"CANCELLED"}
        light_cols = [
            c for c in lls_handle.users_collection if c.name.startswith("LLS_Light")
        ]
        if not light_cols:
            return {"CANCELLED"}

        light_copy = duplicate_collection(light_cols[0], profile_collection)
        lls_handle_copy = next(
            lm for lm in light_copy.objects if lm.name.startswith("LLS_LIGHT_HANDLE")
        )
        base_name = (
            lls_handle.LLStudio.light_name
            or f"Light {lls_handle.LLStudio.order_index}"
        )
        lls_handle_copy.LLStudio.light_name = base_name + " Copy"
        lls_handle_copy.LLStudio.order_index = lls_handle.LLStudio.order_index + 1

        # Bump every light below the source by 1 so the copy lands directly under it.
        for e in props.light_list[lls_handle.LLStudio.order_index + 1 :]:
            obj = bpy.data.objects.get(e.handle_name)
            if obj is not None:
                obj.LLStudio.order_index += 1

        update_light_list_set(context)

        # Mirror the source light's Basic/Advanced visibility onto the copy so
        # only the engine-appropriate sub-light is shown (LayerCollection.exclude
        # defaults to False on freshly created collections, otherwise both
        # would be visible).
        from ..core.scene_utils import find_view_layer

        layer_root = context.view_layer.layer_collection
        src_basic = next(
            (c for c in light_cols[0].children if c.name.startswith("LLS_Basic")),
            None,
        )
        src_advanced = next(
            (c for c in light_cols[0].children if c.name.startswith("LLS_Advanced")),
            None,
        )
        dst_basic = next(
            (c for c in light_copy.children if c.name.startswith("LLS_Basic")),
            None,
        )
        dst_advanced = next(
            (c for c in light_copy.children if c.name.startswith("LLS_Advanced")),
            None,
        )
        for src, dst in ((src_basic, dst_basic), (src_advanced, dst_advanced)):
            if src is None or dst is None:
                continue
            src_view = find_view_layer(src, layer_root)
            dst_view = find_view_layer(dst, layer_root)
            if src_view is not None and dst_view is not None:
                dst_view.exclude = src_view.exclude

        visible_children = [obj for obj in lls_handle_copy.children if obj.visible_get()]
        if visible_children:
            light_object = visible_children[0]
            for o in context.selected_objects:
                o.select_set(False)
            context.view_layer.objects.active = light_object
            light_object.select_set(True)

        # Notify modal control panel if it's open.
        from .modal.control_panel import panel_global, update_light_sets
        if panel_global is not None:
            update_light_sets(panel_global, context, always=True)

        log("light copied")
        return {"FINISHED"}


class LLS_OT_CameraToggleAllLights(bpy.types.Operator):
    bl_idname = "lls.camera_toggle_all_lights"
    bl_label = "Toggle Lights Visibility in Camera"
    bl_description = "Toggle lights visibility in cameras"
    bl_options = {"REGISTER", "UNDO"}

    visible_camera: BoolProperty(name="Ray Visibility")

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.scene.LLStudio.initialized

    def execute(self, context: bpy.types.Context) -> set[str]:
        lls_collection = get_lls_collection(context)
        if lls_collection is None:
            return {"CANCELLED"}
        for col in lls_collection.children_recursive:
            for ob in col.objects:
                if ob.type in {"MESH", "LIGHT"}:
                    ob.visible_camera = self.visible_camera
        return {"FINISHED"}


class LLS_OT_DuplicateMove(bpy.types.Operator):
    bl_idname = "lls_object.duplicate_move"
    bl_label = "Duplicate LLS Light"
    bl_description = "Shift+D wrapper that copies the active LLS light via the LLS-aware path"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return LLS_OT_LightListCopy.poll(context)

    def execute(self, context: bpy.types.Context) -> set[str]:
        return bpy.ops.lls_list.copy_light()


# Re-export helpers so other operators can drive the mute/visible_camera
# get/set callbacks on ``LightListItem`` without circular imports.
def _light_handle_view_layer(context: bpy.types.Context, handle_name: str):
    obj = context.scene.objects.get(handle_name)
    if obj is None:
        return None
    col = get_collection(obj)
    if col is None:
        return None
    return find_view_layer(col, context.view_layer.layer_collection)


def light_item_mute_get(handle_name: str) -> bool:
    vl = _light_handle_view_layer(bpy.context, handle_name)
    if vl is None:
        obj = bpy.data.objects.get(handle_name)
        return bool(obj.LLStudio.mute) if obj else False
    return bool(vl.exclude)


def light_item_mute_set(handle_name: str, value: bool) -> None:
    obj = bpy.context.scene.objects.get(handle_name)
    if obj is None:
        return
    col = get_collection(obj)
    if col is None:
        obj.LLStudio.mute = value
        return
    vl = find_view_layer(col, bpy.context.view_layer.layer_collection)
    if vl is not None:
        vl.exclude = value
    obj.LLStudio.mute = value


def light_item_visible_camera_get(handle_name: str) -> bool:
    obj = bpy.context.scene.objects.get(handle_name)
    if obj is None:
        return False
    return all(o.visible_camera for o in obj.children) if obj.children else True


def light_item_visible_camera_set(handle_name: str, value: bool) -> None:
    obj = bpy.context.scene.objects.get(handle_name)
    if obj is None:
        return
    for o in obj.children:
        o.visible_camera = value


classes: tuple[type[bpy.types.Operator], ...] = (
    LLS_OT_AddLight,
    LLS_OT_DeleteLight,
    LLS_OT_MuteToggle,
    LLS_OT_Isolate,
    LLS_OT_LightListMove,
    LLS_OT_LightListCopy,
    LLS_OT_CameraToggleAllLights,
    LLS_OT_DuplicateMove,
)
