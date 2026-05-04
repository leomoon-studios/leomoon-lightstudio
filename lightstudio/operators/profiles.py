"""Profile system operators (CRUD, constraints, import/export).

Ports legacy ``light_profiles`` operators:

- ``lls_list.{new_profile, delete_profile, copy_profile,
  copy_profile_to_scene, copy_profile_menu, move_profile,
  select_profile_handle, isolate_profile}``
- ``lls_list.{create_profile_constraint,
  constraint_toggle_parent_inverse, remove_constraint}``
- ``lls_list.{import_profiles, export_profiles}``
- ``light_studio.refresh_lightlist``

Scene-duplication detection lives in :mod:`lightstudio.core.profiles`
(``check_profiles_consistency``); each operator calls it on entry just
like the legacy code did.
"""

from __future__ import annotations

import contextlib
import json
import os
import time

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from mathutils import Matrix

from ..core.light_io import get_profile_handle, light_from_dict, salvage_data
from ..core.log import log
from ..core.paths import LLS_BLEND
from ..core.profiles import (
    add_profile_hashes,
    check_profiles_consistency,
    get_hash,
    update_profile_list_index,
)
from ..core.scene_utils import (
    duplicate_collection,
    family,
    get_collection,
    get_lls_collection,
    is_family,
    llscol_profilecol,
    replace_link,
    update_light_list_set,
)

VERSION = 4


def _close_control_panel() -> None:
    try:
        from .modal.control_panel import close_control_panel  # type: ignore
        close_control_panel()
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


class LLS_OT_NewProfile(bpy.types.Operator):
    bl_idname = "lls_list.new_profile"
    bl_label = "Add a new profile"
    bl_options = {"INTERNAL", "UNDO"}

    handle: BoolProperty(default=True)

    def execute(self, context: bpy.types.Context) -> set[str]:
        check_profiles_consistency(context)
        props = context.scene.LLStudio
        item = props.profile_list.add()
        lls_collection = get_lls_collection(context)
        if lls_collection is None:
            self.report({"ERROR"}, "LLS collection missing")
            return {"CANCELLED"}

        if not props.profile_multimode:
            for prof_obj in (
                p
                for p in context.scene.objects
                if p.name.startswith("LLS_PROFILE.") and is_family(p)
            ):
                profile_collection = prof_obj.users_collection[0]
                if profile_collection.name in lls_collection.children:
                    lls_collection.children.unlink(profile_collection)

        idx = 0
        for raw in (
            i.name.split("Profile ")[1]
            for i in props.profile_list
            if i.name.startswith("Profile ")
        ):
            try:
                n = int(raw)
            except ValueError:
                continue
            idx = max(idx, n)
        item.name = f"Profile {idx + 1}"

        # Append the LLS_PROFILE.000 template.
        sep = os.sep
        before = set(bpy.data.objects[:])
        bpy.ops.wm.append(
            filepath=f"{sep}LLS4.blend{sep}Object{sep}",
            directory=f"{LLS_BLEND}{sep}Object{sep}",
            filename="LLS_PROFILE.000",
            active_collection=True,
        )
        after = set(bpy.data.objects[:])
        new = after - before
        if not new:
            self.report({"ERROR"}, "Failed to append LLS_PROFILE.000")
            return {"CANCELLED"}
        profile = new.pop()

        root = next(
            (
                ob
                for ob in context.scene.objects
                if ob.name.startswith("LEOMOON_LIGHT_STUDIO")
            ),
            None,
        )
        if root is not None:
            profile.parent = root
        profile.use_fake_user = True
        profile.hide_select = True

        profile_collection = bpy.data.collections.new(profile.name)
        profile_collection.use_fake_user = True
        lls_collection.children.link(profile_collection)
        replace_link(profile, profile.name)

        item.empty_name = profile.name
        item.enabled = props.profile_multimode

        if self.handle:
            bpy.ops.object.empty_add()
            handle = context.active_object
            handle.name = "LLS_HANDLE"
            handle.empty_display_type = "SPHERE"
            handle.parent = profile
            handle.protected = True
            handle.use_fake_user = True
            handle.lock_rotation[0] = True
            handle.lock_rotation[1] = True
            replace_link(handle, profile.name)

        h = get_hash()
        item.hash = h
        profile["hash"] = h

        props.last_empty = profile.name
        props.profile_list_index = len(props.profile_list) - 1
        update_profile_list_index(props, context, multimode_override=True)
        update_light_list_set(context)
        log("profile added")
        return {"FINISHED"}


class LLS_OT_DeleteProfile(bpy.types.Operator):
    bl_idname = "lls_list.delete_profile"
    bl_label = "Delete the selected profile"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return bool(len(context.scene.LLStudio.profile_list))

    def execute(self, context: bpy.types.Context) -> set[str]:
        check_profiles_consistency(context)
        props = context.scene.LLStudio
        index = props.profile_list_index
        props.profile_list.remove(index)

        if props.last_empty in context.scene.objects:
            obs_to_remove = family(context.scene.objects[props.last_empty])
            collections_to_remove = set()
            for ob in obs_to_remove:
                collections_to_remove.update(ob.users_collection)
                ob.use_fake_user = False
            for ob in obs_to_remove:
                bpy.data.objects.remove(ob)
            for c in collections_to_remove:
                if c.name.startswith("LLS_"):
                    bpy.data.collections.remove(c)

        props.profile_list_index = max(0, index - 1)
        if props.initialized:
            update_light_list_set(context)
        log("profile deleted")
        return {"FINISHED"}


class LLS_OT_CopyProfile(bpy.types.Operator):
    bl_idname = "lls_list.copy_profile"
    bl_label = "Copy profile"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return bool(len(context.scene.LLStudio.profile_list))

    def execute(self, context: bpy.types.Context) -> set[str]:
        check_profiles_consistency(context)
        props = context.scene.LLStudio
        plist = props.profile_list

        _lls, profile_collection = llscol_profilecol(context)
        if profile_collection is None:
            self.report({"ERROR"}, "Active profile collection missing")
            return {"CANCELLED"}

        profile_copy = duplicate_collection(profile_collection, None)
        profile = next(
            ob for ob in profile_copy.objects if ob.name.startswith("LLS_PROFILE")
        )
        handle = next(
            ob for ob in profile.children if ob.name.startswith("LLS_HANDLE")
        )

        for lc in profile_copy.children:
            if not lc.name.startswith("LLS_Light"):
                continue
            for lm in lc.objects:
                if not lm.name.startswith("LLS_LIGHT_MESH"):
                    continue
                cons = lm.constraints.get("Child Of")
                if cons is not None:
                    cons.target = handle
                    cons.inverse_matrix.identity()

        new_item = plist.add()
        new_item.empty_name = profile_copy.name_full
        source_item = plist[props.profile_list_index]
        new_item.name = source_item.name + " Copy"
        new_item.enabled = source_item.enabled
        h = get_hash()
        new_item.hash = h
        profile["hash"] = h

        # Place copy directly after source.
        last = len(plist) - 1
        while last > props.profile_list_index + 1:
            plist.move(last - 1, last)
            last -= 1

        props.profile_list_index += 1
        log("profile copied")
        return {"FINISHED"}


class LLS_OT_MoveProfile(bpy.types.Operator):
    bl_idname = "lls_list.move_profile"
    bl_label = "Move profile"
    bl_options = {"INTERNAL"}

    direction: EnumProperty(items=(("UP", "Up", ""), ("DOWN", "Down", "")))

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return bool(len(context.scene.LLStudio.profile_list))

    def execute(self, context: bpy.types.Context) -> set[str]:
        check_profiles_consistency(context)
        props = context.scene.LLStudio
        plist = props.profile_list
        index = props.profile_list_index
        if self.direction == "DOWN":
            plist.move(index, index + 1)
            new_index = index + 1
        elif self.direction == "UP":
            plist.move(index - 1, index)
            new_index = index - 1
        else:
            return {"CANCELLED"}
        props.profile_list_index = max(0, min(new_index, len(plist) - 1))
        return {"FINISHED"}


class LLS_OT_SelectProfileHandle(bpy.types.Operator):
    bl_idname = "lls_list.select_profile_handle"
    bl_label = "Select Profile's Handle"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        props = context.scene.LLStudio
        if not len(props.profile_list):
            return False
        if props.profile_multimode:
            return props.profile_list[props.profile_list_index].enabled
        return True

    def execute(self, context: bpy.types.Context) -> set[str]:
        check_profiles_consistency(context)
        props = context.scene.LLStudio
        item = props.profile_list[props.profile_list_index]
        for o in context.selected_objects:
            o.select_set(False)
        try:
            handle = next(
                o
                for o in bpy.data.objects[item.empty_name].children
                if o.name.startswith("LLS_HANDLE")
            )
        except (KeyError, StopIteration):
            return {"CANCELLED"}
        handle.hide_viewport = False
        handle.hide_select = False
        handle.hide_set(False)
        context.view_layer.objects.active = handle
        handle.select_set(True)
        return {"FINISHED"}


class LLS_OT_IsolateProfile(bpy.types.Operator):
    bl_idname = "lls_list.isolate_profile"
    bl_label = "Isolate Light Profile"
    bl_options = {"INTERNAL"}

    index: IntProperty()

    def execute(self, context: bpy.types.Context) -> set[str]:
        check_profiles_consistency(context)
        props = context.scene.LLStudio
        enabled_count = sum(p.enabled for p in props.profile_list)
        if enabled_count == 1 and props.profile_list[self.index].enabled:
            for p in props.profile_list:
                p.enabled = True
        else:
            for p in props.profile_list:
                p.enabled = False
            props.profile_list[self.index].enabled = True
        return {"FINISHED"}


class LLS_OT_RefreshLightList(bpy.types.Operator):
    bl_idname = "light_studio.refresh_lightlist"
    bl_label = "Refresh Light List"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        check_profiles_consistency(context)
        update_profile_list_index(
            context.scene.LLStudio, context, multimode_override=True
        )
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Constraint operators
# ---------------------------------------------------------------------------


def _constraint_poll(context: bpy.types.Context) -> bool:
    props = context.scene.LLStudio
    if not len(props.profile_list):
        return False
    if context.mode not in {"POSE", "OBJECT"}:
        return False
    if props.profile_multimode:
        return props.profile_list[props.profile_list_index].enabled
    return True


def _profile_handle_for_active(context: bpy.types.Context) -> bpy.types.Object | None:
    props = context.scene.LLStudio
    item = props.profile_list[props.profile_list_index]
    try:
        return next(
            o
            for o in bpy.data.objects[item.empty_name].children
            if o.name.startswith("LLS_HANDLE")
        )
    except (KeyError, StopIteration):
        return None


class LLS_OT_CreateProfileConstraint(bpy.types.Operator):
    bl_idname = "lls_list.create_profile_constraint"
    bl_label = "Constrain Profile's Handle to Object"
    bl_options = {"INTERNAL", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return _constraint_poll(context)

    def execute(self, context: bpy.types.Context) -> set[str]:
        handle = _profile_handle_for_active(context)
        if handle is None:
            return {"CANCELLED"}
        cons = handle.constraints.new("CHILD_OF")
        cons.name = "LLS Child Of"
        cons.use_location_x = True
        cons.use_location_y = True
        cons.use_location_z = True
        cons.use_rotation_x = False
        cons.use_rotation_y = False
        cons.use_rotation_z = True
        cons.use_scale_x = False
        cons.use_scale_y = False
        cons.use_scale_z = False
        if context.active_object and context.active_object.select_get():
            cons.target = context.active_object
        return {"FINISHED"}


class LLS_OT_ConstraintToggleParentInverse(bpy.types.Operator):
    bl_idname = "lls_list.constraint_toggle_parent_inverse"
    bl_label = "Toggle Constraint's Parent Inverse"
    bl_options = {"INTERNAL", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return _constraint_poll(context)

    def execute(self, context: bpy.types.Context) -> set[str]:
        handle = _profile_handle_for_active(context)
        if handle is None:
            return {"CANCELLED"}
        handle.hide_viewport = False
        handle.hide_select = False
        cons = handle.constraints.get("LLS Child Of")
        if cons is None:
            return {"CANCELLED"}
        if cons.inverse_matrix == Matrix.Identity(4):
            with context.temp_override(constraint=cons, object=handle):
                bpy.ops.constraint.childof_set_inverse(constraint=cons.name)
        else:
            with context.temp_override(constraint=cons, object=handle):
                bpy.ops.constraint.childof_clear_inverse(constraint=cons.name)
        return {"FINISHED"}


class LLS_OT_ConstraintRemove(bpy.types.Operator):
    bl_idname = "lls_list.remove_constraint"
    bl_label = "Remove Constraint"
    bl_options = {"INTERNAL", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return _constraint_poll(context)

    def execute(self, context: bpy.types.Context) -> set[str]:
        handle = _profile_handle_for_active(context)
        if handle is None:
            return {"CANCELLED"}
        cons = handle.constraints.get("LLS Child Of")
        if cons is None:
            return {"CANCELLED"}
        handle.constraints.remove(cons)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Import / export
# ---------------------------------------------------------------------------


_ALLOWED_EXT = {".lls", ".json"}


def _compose_profile(list_index: int) -> dict:
    props = bpy.context.scene.LLStudio
    item = props.profile_list[list_index]
    profile_dict: dict = {
        "name": item.name,
        "lights": [],
    }
    profile = bpy.data.objects[item.empty_name]
    profile_collection = get_collection(profile)
    handle = get_profile_handle(profile)
    if handle is not None:
        profile_dict["handle_position"] = [
            handle.location.x,
            handle.location.y,
            handle.location.z,
        ]
        if "LLS Child Of" in handle.constraints:
            cons = handle.constraints["LLS Child Of"]
            profile_dict["child_constraint"] = (
                cons.target.name if cons.target else "",
                "CLEAR" if cons.inverse_matrix == Matrix.Identity(4) else "SET",
            )
        else:
            profile_dict["child_constraint"] = None
    else:
        profile_dict["handle_position"] = [0.0, 0.0, 0.0]
        profile_dict["child_constraint"] = None

    if profile_collection is not None:
        for light_collection in profile_collection.children:
            try:
                light = salvage_data(light_collection)
                profile_dict["lights"].append(light.dict)
            except Exception:  # noqa: BLE001
                continue
        profile_dict["lights"].sort(key=lambda x: x.get("order_index") or 0)
    return profile_dict


def _parse_profiles(
    context: bpy.types.Context,
    props: bpy.types.PropertyGroup,
    profiles: list[dict],
    version: int = VERSION,
    internal_copy: bool = False,
) -> None:
    plist = props.profile_list
    for profile in profiles:
        bpy.ops.lls_list.new_profile()
        props.profile_list_index = len(plist) - 1
        plist[-1].name = profile["name"]
        if not internal_copy:
            d = time.localtime()
            plist[-1].name += f" {str(d.tm_year)[-2:]}-{d.tm_mon:02}-{d.tm_mday:02} {d.tm_hour:02}:{d.tm_min:02}"

        if profile.get("child_constraint"):
            bpy.ops.lls_list.create_profile_constraint()

        profile_empty = context.scene.objects[plist[-1].empty_name]
        handle = get_profile_handle(profile_empty)
        if version > 1 and handle is not None:
            pos = profile.get("handle_position", [0.0, 0.0, 0.0])
            handle.location.x, handle.location.y, handle.location.z = pos

        for light in profile.get("lights", []):
            if version < 3:
                light["advanced"] = light.copy()
            light_from_dict(light, profile_empty.users_collection[0])


class LLS_OT_ImportProfiles(bpy.types.Operator):
    bl_idname = "lls_list.import_profiles"
    bl_label = "Import profiles"
    bl_description = "Import profiles from file"

    filepath: StringProperty(default="*.lls", subtype="FILE_PATH")

    def execute(self, context: bpy.types.Context) -> set[str]:
        ext = os.path.splitext(self.filepath)[1].lower()
        if ext not in _ALLOWED_EXT:
            self.report(
                {"ERROR"},
                f"Unsupported extension {ext!r}; expected one of "
                f"{sorted(_ALLOWED_EXT)}",
            )
            return {"CANCELLED"}
        if not os.path.isfile(self.filepath):
            self.report({"ERROR"}, f"File not found: {self.filepath}")
            return {"CANCELLED"}
        try:
            with open(self.filepath) as f:
                payload = json.load(f)
        except (OSError, ValueError) as exc:
            self.report({"ERROR"}, f"Failed to read profile file: {exc}")
            return {"CANCELLED"}
        props = context.scene.LLStudio
        _parse_profiles(
            context,
            props,
            payload.get("profiles", []),
            int(float(payload.get("version", VERSION))),
        )
        update_light_list_set(context)
        log("profiles imported")
        return {"FINISHED"}

    def invoke(
        self, context: bpy.types.Context, event: bpy.types.Event
    ) -> set[str]:
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class LLS_OT_ExportProfiles(bpy.types.Operator):
    bl_idname = "lls_list.export_profiles"
    bl_label = "Export profiles to file"
    bl_description = "Export profile(s) to file"

    filepath: StringProperty(default="profile.lls", subtype="FILE_PATH")
    all: BoolProperty(default=False, name="Export All Profiles")

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return bool(len(context.scene.LLStudio.profile_list))

    def execute(self, context: bpy.types.Context) -> set[str]:
        ext = os.path.splitext(self.filepath)[1].lower()
        if ext not in _ALLOWED_EXT:
            self.report(
                {"ERROR"},
                f"Unsupported extension {ext!r}; expected one of "
                f"{sorted(_ALLOWED_EXT)}",
            )
            return {"CANCELLED"}
        props = context.scene.LLStudio
        d = time.localtime()
        export_file: dict = {
            "date": f"{d.tm_year}-{d.tm_mon:02}-{d.tm_mday:02} {d.tm_hour:02}:{d.tm_min:02}",
            "version": VERSION,
            "profiles": [],
        }
        if self.all:
            for p in range(len(props.profile_list)):
                try:
                    export_file["profiles"].append(_compose_profile(p))
                except Exception:  # noqa: BLE001
                    self.report(
                        {"WARNING"},
                        f"Malformed profile {props.profile_list[p].name}. Omitting.",
                    )
        else:
            try:
                export_file["profiles"].append(
                    _compose_profile(props.profile_list_index)
                )
            except Exception:  # noqa: BLE001
                self.report(
                    {"WARNING"},
                    f"Malformed profile "
                    f"{props.profile_list[props.profile_list_index].name}. "
                    "Omitting.",
                )
        try:
            with open(self.filepath, "w") as f:
                json.dump(export_file, f, indent=4)
        except OSError as exc:
            self.report({"ERROR"}, f"Failed to write profile file: {exc}")
            return {"CANCELLED"}
        log("profiles exported")
        return {"FINISHED"}

    def invoke(
        self, context: bpy.types.Context, event: bpy.types.Event
    ) -> set[str]:
        if not self.filepath or self.filepath == "profile.lls":
            self.filepath = "profile.lls"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class LLS_OT_CopyProfileToScene(bpy.types.Operator):
    bl_idname = "lls_list.copy_profile_to_scene"
    bl_label = "Copy Profile to Scene"
    bl_property = "sceneprop"

    def _get_scenes(self, context: bpy.types.Context):
        return ((s.name, s.name, "Scene name") for s in bpy.data.scenes)

    sceneprop: EnumProperty(items=_get_scenes)

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return bool(len(context.scene.LLStudio.profile_list))

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = context.scene.LLStudio
        profiles = [_compose_profile(props.profile_list_index)]
        context.window.scene = bpy.data.scenes[self.sceneprop]
        context.scene.render.engine = "CYCLES"
        if not context.scene.LLStudio.initialized:
            bpy.ops.scene.create_leomoon_light_studio()
        _parse_profiles(
            context, context.scene.LLStudio, profiles, internal_copy=True
        )
        _close_control_panel()
        return {"FINISHED"}

    def invoke(
        self, context: bpy.types.Context, event: bpy.types.Event
    ) -> set[str]:
        context.window_manager.invoke_search_popup(self)
        return {"FINISHED"}


class LLS_OT_CopyProfileMenu(bpy.types.Operator):
    bl_idname = "lls_list.copy_profile_menu"
    bl_label = "Copy selected profile"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return bool(len(context.scene.LLStudio.profile_list))

    def execute(self, context: bpy.types.Context) -> set[str]:
        wm = context.window_manager

        def draw(self, _context):
            layout = self.layout
            layout.operator_context = "INVOKE_AREA"
            col = layout.column(align=True)
            col.operator("lls_list.copy_profile")
            col.operator("lls_list.copy_profile_to_scene")

        wm.popup_menu(draw, title="Copy Profile")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Scene-duplication detection (msgbus + load_post)
# ---------------------------------------------------------------------------


_owner = object()


def _msgbus_callback(*_args) -> None:
    active_object = bpy.context.active_object
    props = bpy.context.scene.LLStudio
    if (
        not active_object
        or not props.initialized
        or not props.profile_multimode
        or not active_object.name.startswith("LLS_LIGHT_")
    ):
        return
    from ..core.scene_utils import find_light_profile_object

    profile = find_light_profile_object(active_object)
    if profile is None:
        return
    props.profile_list_index = min(
        len(props.profile_list) - 1, props.profile_list_index
    )
    list_profile = props.profile_list[props.profile_list_index]
    if profile.name != list_profile.empty_name:
        for i, p in enumerate(props.profile_list):
            if p.empty_name == profile.name:
                props.profile_list_index = i
                break


def _subscribe_msgbus() -> None:
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.LayerObjects, "active"),
        owner=_owner,
        args=(),
        notify=_msgbus_callback,
    )


@bpy.app.handlers.persistent
def _load_post(_dummy) -> None:
    _subscribe_msgbus()
    bpy.app.timers.register(add_profile_hashes, first_interval=0.1)


def register_handlers() -> None:
    if _load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post)
    _subscribe_msgbus()
    with contextlib.suppress(Exception):  # noqa: BLE001
        bpy.app.timers.register(add_profile_hashes, first_interval=0.1)


def unregister_handlers() -> None:
    if _load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post)
    bpy.msgbus.clear_by_owner(_owner)


classes: tuple[type[bpy.types.Operator], ...] = (
    LLS_OT_NewProfile,
    LLS_OT_DeleteProfile,
    LLS_OT_CopyProfile,
    LLS_OT_MoveProfile,
    LLS_OT_SelectProfileHandle,
    LLS_OT_IsolateProfile,
    LLS_OT_RefreshLightList,
    LLS_OT_CreateProfileConstraint,
    LLS_OT_ConstraintToggleParentInverse,
    LLS_OT_ConstraintRemove,
    LLS_OT_ImportProfiles,
    LLS_OT_ExportProfiles,
    LLS_OT_CopyProfileToScene,
    LLS_OT_CopyProfileMenu,
)
