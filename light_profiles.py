import bpy
from bpy.props import BoolProperty, StringProperty, EnumProperty, IntProperty
import os, sys, subprocess

from . common import *
from . light_data import *
from . operators.modal import close_control_panel
from . import light_list
from mathutils import Matrix

_ = os.sep

from time import time_ns
import random
def get_hash():
    return str(time_ns()) + ''.join(random.choice('0123456789ABCDEFGHIJKLMNOPRSTUWXYZ') for i in range(4))
def add_profile_hashes():
    scene_profiles = {profile for scene in bpy.data.scenes for profile in scene.LLStudio.profile_list}
    for profile in scene_profiles:
        try:
            profile_root = bpy.data.objects[profile.empty_name]
            if not profile.hash or not 'hash' in profile_root:
                # add new hash
                hash = get_hash()
                profile.hash = profile_root['hash'] = hash
        except Exception as e:
            if VERBOSE: print("Malformed profiles are not processed here.", e)

def check_profiles_consistency(context, invert_multimode=False):
    # Check for doubled profiles in the current scene. Assume that if current profile is doubled, then all profiles of this scene are doubled
    changed = False
    if len(context.scene.LLStudio.profile_list):
        list_props = context.scene.LLStudio
        scene_profile_list = list_props.profile_list
        profile_menu_item = scene_profile_list[context.scene.LLStudio.profile_list_index]
        profile_empty_idx = bpy.data.objects.find(profile_menu_item.empty_name)
        lls = [o for o in context.scene.objects if o.name.startswith('LEOMOON_LIGHT_STUDIO')][0]
        if (not invert_multimode and not list_props.profile_multimode) or (invert_multimode and list_props.profile_multimode):
            if profile_empty_idx != -1:
                try:
                    this_scene_profiles = (o for o in lls.children if o.name.startswith('LLS_PROFILE') and o.name in context.scene.objects)
                    this_profile_root = next(this_scene_profiles)
                    if this_profile_root.name != profile_menu_item.empty_name:
                        if VERBOSE: print('#', profile_menu_item.name, profile_menu_item.empty_name, this_profile_root.name)
                        profile_menu_item.empty_name = this_profile_root.name
                        hash = get_hash()
                        profile_menu_item.hash = this_profile_root['hash'] = hash
                        changed = True

                        # assume the scene was duplicated
                        # keep the active profile (as its hierarchy was duped) and remove all other profiles from the list (as they link to the original objects)
                        # while len(scene_profile_list) > 1 and scene_profile_list[0] != profile_menu_item:
                        #     scene_profile_list.remove(0)
                        # while len(scene_profile_list) > 1:
                        #     scene_profile_list.remove(1)


                        for prof in scene_profile_list:
                            if prof == profile_menu_item: continue
                            prof_collection = get_collection(bpy.data.objects[prof.empty_name])

                            col = duplicate_collection(prof_collection, None)
                            new_root = next(ob for ob in col.objects if ob.name.startswith("LLS_PROFILE"))
                            if VERBOSE: print('##', prof.name, prof.empty_name, new_root.name)
                            prof.empty_name = new_root.name
                            hash = get_hash()
                            prof.hash = new_root['hash'] = hash
                            changed = True
                except Exception as e:
                    print("Something wrong with object hierarchy. Profile consistency check failed.", e)
            else:
                print("profile root not found")
        elif (not invert_multimode and list_props.profile_multimode) or (invert_multimode and not list_props.profile_multimode):
            try:
                enabled_profiles = [prof for prof in scene_profile_list if prof.enabled]
                disabled_profiles = [prof for prof in scene_profile_list if not prof.enabled]
                duped = False
                for prof in enabled_profiles:
                    this_scene_profiles = (o for o in lls.children if o.name.startswith('LLS_PROFILE') and o.name in context.scene.objects and 'hash' in o and o['hash'] == prof.hash)
                    this_profile_root = next(this_scene_profiles)
                    if this_profile_root.name != prof.empty_name:
                        if VERBOSE: print('M#', prof.name, prof.empty_name, this_profile_root.name)
                        prof.empty_name = this_profile_root.name
                        hash = get_hash()
                        prof.hash = this_profile_root['hash'] = hash
                        changed = duped = True
                # assume all profiles to be duped if any visible profile is duped
                if duped:
                    for prof in disabled_profiles:
                        prof_collection = get_collection(bpy.data.objects[prof.empty_name])

                        col = duplicate_collection(prof_collection, None)
                        new_root = next(ob for ob in col.objects if ob.name.startswith("LLS_PROFILE"))
                        if VERBOSE: print('M##', prof.name, prof.empty_name, new_root.name)
                        prof.empty_name = new_root.name
                        hash = get_hash()
                        prof.hash = new_root['hash'] = hash
            except Exception as e:
                print("Something wrong with object hierarchy. Multi-Profile consistency check failed.", e)
    return changed

class LLS_OT_RefreshLightList(bpy.types.Operator):
    bl_idname = "light_studio.refresh_lightlist"
    bl_label = "Refresh Light List"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        check_profiles_consistency(context)
        _update_profile_list_index(context.scene.LLStudio, context, multimode_override=True)
        return {"FINISHED"}

class ListItem(bpy.types.PropertyGroup):
    """ Group of properties representing an item in the list """
    def update_name(self, context):
        print("{} : {}".format(repr(self.name), repr(context)))

    name: StringProperty(
            name="Profile Name",
            default="Untitled")

    empty_name: StringProperty(
            name="Name of Empty that holds the profile",
            description="",
            default="")

    hash: StringProperty()

    def enabled_update_func(self, context):
        if self.empty_name not in bpy.data.objects: return
        profile_collection = get_collection(bpy.data.objects[self.empty_name])
        profile_list_index = int(self.path_from_id().split('[')[1].split(']')[0])

        lls_collection = get_lls_collection(context)
        if self.enabled:
            #link selected profile
            if bpy.data.collections[self.empty_name].name not in lls_collection.children:
                lls_collection.children.link(bpy.data.collections[self.empty_name])

            props = context.scene.LLStudio
            light_list.update_light_list_set(context, profile_idx=profile_list_index)

        else:
            #unlink profile
            if profile_collection:
                if profile_collection.name in lls_collection.children:
                    lls_collection.children.unlink(profile_collection)
            light_list.update_light_list_set(context)


    enabled: BoolProperty(default=False, update=enabled_update_func)

class LLS_UL_ProfileList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        props = context.scene.LLStudio
        custom_icon = 'OUTLINER_OB_LIGHT' if item.enabled else 'LIGHT'
        # Make sure your code supports all 3 layout types
        if (not data.profile_multimode and data.profile_list[data.profile_list_index].empty_name in context.scene.objects)\
            or (data.profile_multimode and len([profile for scene in bpy.data.scenes for profile in scene.LLStudio.profile_list if profile.empty_name==data.profile_list[index].empty_name]) == 1):
            if self.layout_type in {'DEFAULT', 'COMPACT'}:
                layout.prop(item, 'name', text='', emboss=False, translate=False)
                if props.profile_multimode:
                    layout.prop(item, 'enabled', text='', emboss=False, translate=False, icon=custom_icon)

                    enabled_count = 0
                    for p in props.profile_list:
                        enabled_count += p.enabled

                    custom_solo_icon = 'SOLO_ON' if enabled_count == 1 and item.enabled else 'SOLO_OFF'
                    layout.operator('lls_list.isolate_profile', emboss=False, icon=custom_solo_icon, text="").index = index

            elif self.layout_type in {'GRID'}:
                layout.alignment = 'CENTER'
                layout.label("", icon = custom_icon)
        else:
            layout.operator('light_studio.refresh_lightlist', text="Refresh...")

class LIST_OT_IsolateProfile(bpy.types.Operator):

    bl_idname = "lls_list.isolate_profile"
    bl_label = "Isolate Light Profile"
    bl_options = {"INTERNAL"}

    index: IntProperty()

    def execute(self, context):
        check_profiles_consistency(context)
        props = context.scene.LLStudio

        enabled_count = 0
        for p in props.profile_list:
            enabled_count += p.enabled

        if enabled_count == 1 and props.profile_list[self.index].enabled:
            for p in props.profile_list:
                p.enabled = True
        else:
            for p in props.profile_list:
                p.enabled = False

            props.profile_list[self.index].enabled = True


        return{'FINISHED'}

class LIST_OT_NewItem(bpy.types.Operator):

    bl_idname = "lls_list.new_profile"
    bl_label = "Add a new profile"
    bl_options = {"INTERNAL", "UNDO"}

    handle: BoolProperty(default=True)

    def execute(self, context):
        check_profiles_consistency(context)
        props = context.scene.LLStudio
        item = props.profile_list.add()
        lls_collection = get_lls_collection(context)

        if not props.profile_multimode:
            # unlink existing profiles
            for profile in (prof for prof in context.scene.objects if prof.name.startswith('LLS_PROFILE.') and isFamily(prof)):
                profile_collection = profile.users_collection[0]
                lls_collection.children.unlink(profile_collection)
            #

        idx = 0
        for id in (i.name.split('Profile ')[1] for i in props.profile_list if i.name.startswith('Profile ')):
            try:
                id = int(id)
            except ValueError:
                continue

            if id > idx: idx = id

        item.name = 'Profile '+str(idx+1)

        ''' Add Hierarchy stuff '''
        # before
        A = set(bpy.data.objects[:])

        script_file = os.path.realpath(__file__)
        dir = os.path.dirname(script_file)
        bpy.ops.wm.append(filepath=_+'LLS4.blend'+_+'Object'+_,
            directory=os.path.join(dir,"LLS4.blend"+_+"Object"+_),
            filename="LLS_PROFILE.000",
            active_collection=True)

        # after operation
        B = set(bpy.data.objects[:])

        # whats the difference
        profile = (A ^ B).pop()

        profile.parent = [ob for ob in context.scene.objects if ob.name.startswith('LEOMOON_LIGHT_STUDIO')][0]
        profile.use_fake_user = True
        profile.hide_select = True
        profile_collection = bpy.data.collections.new(profile.name)
        profile_collection.use_fake_user = True
        lls_collection = [c for c in context.scene.collection.children if c.name.startswith('LLS')][0]
        lls_collection.children.link(profile_collection)
        replace_link(profile, profile.name)

        item.empty_name = profile.name
        item.enabled = props.profile_multimode

        handle = None
        if self.handle:
            bpy.ops.object.empty_add()
            handle = context.active_object
            handle.name = "LLS_HANDLE"
            handle.empty_display_type = 'SPHERE'
            handle.parent = profile
            handle.protected = True
            handle.use_fake_user = True
            handle.lock_rotation[0] = True
            handle.lock_rotation[1] = True
            replace_link(handle, profile.name)

        props.last_empty = profile.name
        props.profile_list_index = len(props.profile_list)-1
        _update_profile_list_index(props, context, multimode_override=True)

        light_list.update_light_list_set(context)

        return{'FINISHED'}

class LIST_OT_DeleteItem(bpy.types.Operator):

    bl_idname = "lls_list.delete_profile"
    bl_label = "Delete the selected profile"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list """
        return len(context.scene.LLStudio.profile_list)

    def execute(self, context):
        check_profiles_consistency(context)
        props = context.scene.LLStudio
        index = props.profile_list_index

        props.profile_list.remove(index)

        ''' Delete/Switch Hierarchy stuff '''
        #delete objects from current profile
        if props.last_empty not in context.scene.objects:
            # update index
            props.profile_list_index = max(0, index-1)
            return {'FINISHED'}
        obsToRemove = family(context.scene.objects[props.last_empty])
        collectionsToRemove = set()
        for ob in obsToRemove:
            collectionsToRemove.update(ob.users_collection)
            ob.use_fake_user = False

        for obj in obsToRemove:
            bpy.data.objects.remove(obj)

        for c in collectionsToRemove:
            if c.name.startswith('LLS_'):
                bpy.data.collections.remove(c)

        # update index
        props.profile_list_index = max(0, index-1)

        if props.initialized:
            light_list.update_light_list_set(context)

        return {'FINISHED'}

class LIST_OT_CopyItem(bpy.types.Operator):

    bl_idname = "lls_list.copy_profile"
    bl_label = "Copy profile"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list. """
        return len(context.scene.LLStudio.profile_list)

    def execute(self, context):
        check_profiles_consistency(context)
        props = context.scene.LLStudio
        list = props.profile_list

        lls_collection, profile_collection = llscol_profilecol(context)

        profile_copy = duplicate_collection(profile_collection, None)
        profile = [ob for ob in profile_copy.objects if ob.name.startswith('LLS_PROFILE')][0]
        handle = [ob for ob in profile.children if ob.name.startswith('LLS_HANDLE')][0]

        for l in [lm for lc in profile_copy.children if lc.name.startswith('LLS_Light') for lm in lc.objects if lm.name.startswith('LLS_LIGHT_MESH')]:
            l.constraints['Child Of'].target = handle
            l.constraints['Child Of'].inverse_matrix.identity()
            # l.constraints['Child Of'].use_rotation_x = False
            # l.constraints['Child Of'].use_rotation_y = False

        new_list_item = props.profile_list.add()
        new_list_item.empty_name = profile_copy.name_full
        profile_list_item = props.profile_list[props.profile_list_index]
        new_list_item.name = profile_list_item.name + ' Copy'
        new_list_item.enabled = profile_list_item.enabled
        hash = get_hash()
        new_list_item.hash = profile['hash'] = hash

        # place copied profile next to source profile
        lastItemId = len(props.profile_list)-1
        while lastItemId > props.profile_list_index+1:
            list.move(lastItemId-1, lastItemId)
            lastItemId -= 1

        props.profile_list_index += 1

        return{'FINISHED'}

class LIST_OT_SelectProfileHandle(bpy.types.Operator):
    '''Select profile's handle'''
    bl_idname = "lls_list.select_profile_handle"
    bl_label = "Select Profile's Handle"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list. """
        props = context.scene.LLStudio
        list = props.profile_list
        index = props.profile_list_index
        if props.profile_multimode:
            return len(list) and list[index].enabled
        else:
            return len(list)

    def execute(self, context):
        check_profiles_consistency(context)
        props = context.scene.LLStudio
        list = props.profile_list
        index = props.profile_list_index

        for o in context.selected_objects:
            o.select_set(False)

        handle = [o for o in bpy.data.objects[list[index].empty_name].children if o.name.startswith("LLS_HANDLE")][0]
        handle.hide_viewport = False
        handle.hide_select = False
        handle.hide_set(False)
        context.view_layer.objects.active = handle
        handle.select_set(True)

        return{'FINISHED'}

class LIST_OT_CreateProfileConstraint(bpy.types.Operator):
    ''' Parent profile's handle via 'child of' constraint '''
    bl_idname = "lls_list.create_profile_constraint"
    bl_label = "Constrain Profile's Handle to Object"
    bl_options = {"INTERNAL", "UNDO"}

    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list. """
        props = context.scene.LLStudio
        list = props.profile_list
        index = props.profile_list_index
        if props.profile_multimode:
            return (context.mode in {'POSE', 'OBJECT'}) and len(list) and list[index].enabled
        else:
            return (context.mode in {'POSE', 'OBJECT'}) and len(list)

    def execute(self, context):
        # check_profiles_consistency(context)
        props = context.scene.LLStudio
        list = props.profile_list
        index = props.profile_list_index

        handle: bpy.types.Object = [o for o in bpy.data.objects[list[index].empty_name].children if o.name.startswith("LLS_HANDLE")][0]
        # handle.hide_viewport = False
        # handle.hide_select = False
        # context.view_layer.objects.active = handle
        # handle.select_set(True)

        cons = handle.constraints.new('CHILD_OF')
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

        return{'FINISHED'}

class LIST_OT_ConstraintToggleParentInverse(bpy.types.Operator):
    ''' Toggle constraint parent inverse '''
    bl_idname = "lls_list.constraint_toggle_parent_inverse"
    bl_label = "Toggle Constraint's Parent Inverse"
    bl_options = {"INTERNAL", "UNDO"}

    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list. """
        props = context.scene.LLStudio
        list = props.profile_list
        index = props.profile_list_index
        if props.profile_multimode:
            return (context.mode in {'POSE', 'OBJECT'}) and len(list) and list[index].enabled
        else:
            return (context.mode in {'POSE', 'OBJECT'}) and len(list)

    def execute(self, context):
        # check_profiles_consistency(context)
        props = context.scene.LLStudio
        list = props.profile_list
        index = props.profile_list_index

        handle: bpy.types.Object = [o for o in bpy.data.objects[list[index].empty_name].children if o.name.startswith("LLS_HANDLE")][0]
        handle.hide_viewport = False
        handle.hide_select = False

        cons = handle.constraints["LLS Child Of"]
        context_copy = bpy.context.copy()
        context_copy["constraint"] = cons
        if cons.inverse_matrix == Matrix.Identity(4):
            with context.temp_override(constraint=cons, object=handle):
                bpy.ops.constraint.childof_set_inverse(constraint=cons.name)
        else:
            with context.temp_override(constraint=cons, object=handle):
                bpy.ops.constraint.childof_clear_inverse(constraint=cons.name)

        return{'FINISHED'}

class LIST_OT_ConstraintRemove(bpy.types.Operator):
    ''' Remove constraint '''
    bl_idname = "lls_list.remove_constraint"
    bl_label = "Remove Constraint"
    bl_options = {"INTERNAL", "UNDO"}

    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list. """
        props = context.scene.LLStudio
        list = props.profile_list
        index = props.profile_list_index
        if props.profile_multimode:
            return (context.mode in {'POSE', 'OBJECT'}) and len(list) and list[index].enabled
        else:
            return (context.mode in {'POSE', 'OBJECT'}) and len(list)

    def execute(self, context):
        # check_profiles_consistency(context)
        props = context.scene.LLStudio
        list = props.profile_list
        index = props.profile_list_index

        handle: bpy.types.Object = [o for o in bpy.data.objects[list[index].empty_name].children if o.name.startswith("LLS_HANDLE")][0]

        cons = handle.constraints["LLS Child Of"]
        handle.constraints.remove(cons)

        return{'FINISHED'}

class LIST_OT_MoveItem(bpy.types.Operator):

    bl_idname = "lls_list.move_profile"
    bl_label = "Move profile"
    bl_options = {"INTERNAL"}

    direction: bpy.props.EnumProperty(
                items=(
                    ('UP', 'Up', ""),
                    ('DOWN', 'Down', ""),))

    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list. """
        return len(context.scene.LLStudio.profile_list)


    def move_index(self, context):
        """ Move index of an item render queue while clamping it. """
        props = context.scene.LLStudio
        index = props.profile_list_index
        list_length = len(props.profile_list) - 1 # (index starts at 0)
        new_index = 0

        if self.direction == 'UP':
            new_index = index - 1
        elif self.direction == 'DOWN':
            new_index = index + 1

        new_index = max(0, min(new_index, list_length))
        props.profile_list_index = new_index


    def execute(self, context):
        check_profiles_consistency(context)
        props = context.scene.LLStudio
        list = props.profile_list
        index = props.profile_list_index

        if self.direction == 'DOWN':
            neighbor = index + 1
            list.move(index,neighbor)
        elif self.direction == 'UP':
            neighbor = index - 1
            list.move(neighbor, index)
        else:
            return{'CANCELLED'}
        self.move_index(context)

        return{'FINISHED'}

def _update_profile_list_index(props, context, multimode_override=False):
    if len(props.profile_list) == 0 or props.profile_list_index >= len(props.profile_list): return

    selected_profile = props.profile_list[props.profile_list_index]
    if selected_profile.empty_name not in bpy.data.collections:
        props.profile_list.remove(props.profile_list_index)
        context_show_popup(context, text="Profile collection not found. Profile removed from the list.", title="Error", icon='ERROR')


    if not multimode_override and selected_profile.empty_name == props.last_empty: return

    print('Index update {}'.format(props.profile_list_index))

    if not props.profile_multimode:
        #unlink current profile
        lls_collection = get_lls_collection(context)
        profile_collections = [c for c in lls_collection.children if c.name.startswith('LLS_PROFILE')]

        for col in profile_collections:
            lls_collection.children.unlink(col)

        #link selected profile
        new_profile_collection = bpy.data.collections[selected_profile.empty_name]
        lls_collection.children.link(new_profile_collection)
        # restore lights visibility
        for col in new_profile_collection.children:
            light_handle = next(o for o in col.objects if o.name.startswith('LLS_LIGHT_HANDLE'))
            if light_handle.LLStudio.mute:
                find_view_layer(col, context.view_layer.layer_collection).exclude = light_handle.LLStudio.mute

    props.last_empty = selected_profile.empty_name

    from . operators.modal import update_light_sets, panel_global
    if panel_global:
        update_light_sets(panel_global, bpy.context, always=True)

    light_list.update_light_list_set(context)

    if props.profile_multimode:
        if len(props.light_list):
            handle = bpy.data.objects[props.light_list[0].handle_name]

            for l in props.light_list:
                light_handle = bpy.data.objects[l.handle_name]
                light_objects = [c for c in light_handle.children if c.visible_get()]
                if light_objects and light_objects[0].select_get():
                    context.view_layer.objects.active = light_objects[0]
                    for ob in context.selected_objects:
                        if ob is not light_objects[0]:
                            ob.select_set(False)
                    return

            light_objects = [c for c in handle.children if c.visible_get()]
            if light_objects:
                for ob in context.selected_objects:
                    ob.select_set(False)
                context.view_layer.objects.active = light_objects[0]
                light_objects[0].select_set(True)

def update_profile_list_index(props, context):
    _update_profile_list_index(props, context)

# import/export
import json, time
script_file = os.path.realpath(__file__)
dir = os.path.dirname(script_file)
VERSION = 4
from . import light_operators
def parse_profile(context, props, profiles, version=VERSION, internal_copy=False):
    plist = props.profile_list
    for profile in profiles:
        if VERBOSE:
            print('_'*5, 'Parse profile', '_'*5)
            print(json.dumps(profile, indent=4, separators=(',', ': ')))

        bpy.ops.lls_list.new_profile()
        props.profile_list_index = len(plist)-1
        plist[-1].name = profile["name"]
        if not internal_copy:
            date = time.localtime()
            plist[-1].name += ' {}-{:02}-{:02} {:02}:{:02}'.format(str(date.tm_year)[-2:], date.tm_mon, date.tm_mday, date.tm_hour, date.tm_min)

        child_constraint = profile.get("child_constraint", None)
        if child_constraint:
            bpy.ops.lls_list.create_profile_constraint()

        profile_empty = context.scene.objects[plist[-1].empty_name]

        if version > 1:
            handle = getProfileHandle(profile_empty)
            handle.location.x = profile['handle_position'][0]
            handle.location.y = profile['handle_position'][1]
            handle.location.z = profile['handle_position'][2]

        for light in profile["lights"]:
            if version < 3:
                # most of light settings are moved to advanced sub dict. copy whole dict for the simplicity sake
                light['advanced'] = light.copy()
            light_operators.light_from_dict(light, profile_empty.users_collection[0])

class ImportProfiles(bpy.types.Operator):

    bl_idname = "lls_list.import_profiles"
    bl_label = "Import profiles"
    bl_description = "Import profiles from file"
    #bl_options = {"INTERNAL"}

    filepath: bpy.props.StringProperty(default="*.lls", subtype="FILE_PATH")

    @classmethod
    def poll(self, context):
        return True

    def execute(self, context):
        props = context.scene.LLStudio

        with open(self.filepath, 'r') as f:
            file = f.read()
        f.closed

        file = json.loads(file)
        parse_profile(context, props, file["profiles"], float(file["version"]))
        light_list.update_light_list_set(context)

        return{'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


def compose_profile(list_index):
    props = bpy.context.scene.LLStudio
    profile_dict = {}
    profile_dict['name'] = props.profile_list[list_index].name
    profile_dict['lights']= []
    profile = bpy.data.objects[props.profile_list[list_index].empty_name]
    profile_collection = get_collection(profile)
    handle = getProfileHandle(profile)
    profile_dict['handle_position'] = [handle.location.x, handle.location.y, handle.location.z]

    if "LLS Child Of" in handle.constraints:
        cons = handle.constraints["LLS Child Of"]
        # (target, parent inverse correction)
        profile_dict['child_constraint'] = (cons.target.name, "CLEAR" if cons.inverse_matrix == Matrix.Identity(4) else "SET")
    else:
        profile_dict['child_constraint'] = None

    for light_collection in profile_collection.children:
        light = salvage_data(light_collection)
        profile_dict['lights'].append(light.dict)
        profile_dict['lights'].sort(key=lambda x: x["order_index"])

        # import json
        # print(json.dumps(profile_dict, indent=4, separators=(',', ': ')))
    return profile_dict

class ExportProfiles(bpy.types.Operator):

    bl_idname = "lls_list.export_profiles"
    bl_label = "Export profiles to file"
    bl_description = "Export profile(s) to file"
    #bl_options = {"INTERNAL"}

    filepath: bpy.props.StringProperty(default="profile.lls", subtype="FILE_PATH")
    all: bpy.props.BoolProperty(default=False, name="Export All Profiles")

    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list """
        return len(context.scene.LLStudio.profile_list)

    def execute(self, context):
        props = context.scene.LLStudio
        index = props.profile_list_index

        export_file = {}
        date = time.localtime()
        export_file['date'] = '{}-{:02}-{:02} {:02}:{:02}'.format(date.tm_year, date.tm_mon, date.tm_mday, date.tm_hour, date.tm_min)
        export_file['version'] = VERSION
        profiles_to_export = export_file['profiles'] = []

        if self.all:
            for p in range(len(props.profile_list)):
                try:
                    profiles_to_export.append(compose_profile(p))
                except Exception:
                    self.report({'WARNING'}, 'Malformed profile %s. Omitting.' % props.profile_list[p].name)
        else:
            try:
                profiles_to_export.append(compose_profile(index))
            except Exception:
                self.report({'WARNING'}, 'Malformed profile %s. Omitting.' % props.profile_list[index].name)

        with open(self.filepath, 'w') as f:
            f.write(json.dumps(export_file, indent=4))
        f.closed

        return{'FINISHED'}

    def invoke(self, context, event):
        self.filepath = "profile.lls"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class FindMissingTextures(bpy.types.Operator):

    bl_idname = "lls.find_missing_textures"
    bl_label = "Find Missing Textures"
    bl_description = "Find missing light textures"
    #bl_options = {"INTERNAL"}

    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list """
        return len(context.scene.LLStudio.profile_list)

    def execute(self, context):
        bpy.ops.file.find_missing_files(directory=os.path.join(dir, "textures_real_lights"))
        bpy.context.scene.frame_current = bpy.context.scene.frame_current
        return{'FINISHED'}

class OpenTexturesFolder(bpy.types.Operator):

    bl_idname = "lls.open_textures_folder"
    bl_label = "Open Textures Folder"
    bl_description = "Open textures folder"
    #bl_options = {"INTERNAL"}

    #@classmethod
    #def poll(self, context):
    #    """ Enable if there's something in the list """
    #    return len(context.scene.LLStudio.profile_list)

    def execute(self, context):
        path = os.path.join(dir, "textures_real_lights")
        if sys.platform == 'darwin':
            subprocess.Popen(["open", path])
        elif sys.platform == 'linux2':
            subprocess.Popen(["xdg-open", path])
        elif sys.platform == 'win32':
            subprocess.Popen(["explorer", path])
        return{'FINISHED'}

class CopyProfileToScene(bpy.types.Operator):
    """ Copy Light Profile to Scene """

    bl_idname = "lls_list.copy_profile_to_scene"
    bl_label = "Copy Profile to Scene"
    bl_property = "sceneprop"

    def get_scenes(self, context):
        return ((s.name, s.name, "Scene name") for i,s in enumerate(bpy.data.scenes))#global_vars["scenes"]

    sceneprop: EnumProperty(items = get_scenes)

    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list """
        return len(context.scene.LLStudio.profile_list)

    def execute(self, context):
        props = context.scene.LLStudio
        index = props.profile_list_index

        profiles = [compose_profile(index),]

        context.window.scene = bpy.data.scenes[self.sceneprop]

        context.scene.render.engine = 'CYCLES'
        if not context.scene.LLStudio.initialized:
            bpy.ops.scene.create_leomoon_light_studio()

        parse_profile(context, context.scene.LLStudio, profiles, internal_copy=True)

        close_control_panel()

        return{'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}


class CopyProfileMenu(bpy.types.Operator):

    bl_idname = "lls_list.copy_profile_menu"
    bl_label = "Copy selected profile"

    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list """
        return len(context.scene.LLStudio.profile_list)

    def execute(self, context):
        wm = context.window_manager
        def draw(self, context):
            layout = self.layout
            layout.operator_context='INVOKE_AREA'
            col = layout.column(align=True)
            col.operator('lls_list.copy_profile')
            col.operator('lls_list.copy_profile_to_scene')

        wm.popup_menu(draw, title="Copy Profile")
        return {'FINISHED'}


def msgbus_callback(*args):
    active_object = bpy.context.active_object
    props = bpy.context.scene.LLStudio

    if not active_object or not props.initialized or not props.profile_multimode or not active_object.name.startswith('LLS_LIGHT_'):
        return

    multiprofile_conditions = True
    profile = findLightProfileObject(active_object)
    props.profile_list_index = min(len(props.profile_list)-1, props.profile_list_index)
    list_profile = props.profile_list[props.profile_list_index]
    # multiprofile_conditions = list_profile.enabled and profile and profile.name == list_profile.empty_name
    if not profile.name == list_profile.empty_name:
        for i, p in enumerate(props.profile_list):
            if p.empty_name == profile.name:
                props.profile_list_index = i
                break


owner = object()
subscribe_to = bpy.types.LayerObjects, "active"

from bpy.app.handlers import persistent
@persistent
def lightstudio_load_post(load_handler):
    bpy.msgbus.subscribe_rna(
        key=subscribe_to,
        owner=owner,
        args=(),
        notify=msgbus_callback,
    )
    bpy.app.timers.register(lambda : add_profile_hashes(), first_interval=0.1)

def register():
    bpy.app.handlers.load_post.append(lightstudio_load_post)
    lightstudio_load_post(None)
    bpy.app.timers.register(lambda : add_profile_hashes(), first_interval=0.1)


def unregister():
    bpy.msgbus.clear_by_owner(owner)
    bpy.app.handlers.load_post.remove(lightstudio_load_post)