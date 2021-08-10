import bpy
from bpy.props import BoolProperty, StringProperty, PointerProperty, FloatProperty, EnumProperty, IntProperty
import os, sys, subprocess
from . common import *
from itertools import chain
from . operators import modal
from . operators.modal import close_control_panel, update_light_sets
from . operators.modal_utils import send_light_to_top, LightImage
from . light_data import *

_ = os.sep

class LightListItem(bpy.types.PropertyGroup):
    """ Group of properties representing an item in the list """
    def update_name(self, context):
        name = self.name
        if self.name == '':
            name = self.handle_name
            self.name = name
        bpy.data.objects[self.handle_name].LLStudio.light_name = name

    name: StringProperty(
            name="Profile Name",
            default="Untitled",
            update=update_name)
    
    handle_name: StringProperty(
            description="",
            default="")

class LLS_UL_LightList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        custom_icon = 'OUTLINER_OB_LIGHT' if index == context.scene.LLStudio.profile_list_index else 'LIGHT'

        if item.handle_name in context.scene.objects:
            # Make sure your code supports all 3 layout types
            if self.layout_type in {'DEFAULT', 'COMPACT'}:
                layout.prop(item, 'name', text='', emboss=False, translate=False)

                mesh_object = context.scene.objects[item.handle_name]
                mesh_collection = get_collection(mesh_object)

                view_layer = find_view_layer(mesh_collection, context.view_layer.layer_collection)
                icon = 'LIGHT' if view_layer.exclude else 'OUTLINER_OB_LIGHT'
                layout.operator('light_studio.mute_toggle', emboss=False, icon=icon, text="").index = index

                
                props = context.scene.LLStudio
                excluded=0
                for li in props.light_list:
                    if not li.handle_name in context.scene.objects:
                        continue
                    mesh_object = context.scene.objects[li.handle_name]
                    mesh_collection = get_collection(mesh_object)
                    vl = find_view_layer(mesh_collection, context.view_layer.layer_collection)
                    excluded += vl.exclude
                
                icon = 'SOLO_ON' if excluded == len(props.light_list)-1 and not view_layer.exclude else 'SOLO_OFF'
                layout.operator('light_studio.isolate', emboss=False, icon=icon, text="").index = index

            elif self.layout_type in {'GRID'}:
                layout.alignment = 'CENTER'
                layout.label("", icon = custom_icon)

def get_list_index(self):
    ob = bpy.context.view_layer.objects.active
    if isFamily(ob):
        for i, li in enumerate(self.light_list):
            if ob.parent == None:
                continue
            if li.handle_name == ob.parent.name:
                return i
    return -1

def set_list_index(self, index):
    selected_light = self.light_list[index]
    light_handle = bpy.context.scene.objects[selected_light.handle_name]       # Get the object

    light_collection = light_handle.users_collection[0]
    light_layer = find_view_layer(light_collection, bpy.context.view_layer.layer_collection)
    if light_layer.exclude:
        return
    
    bpy.ops.object.select_all(action='DESELECT') # Deselect all objects

    try:
        basic_light_collection = [c for c in light_collection.children if c.name.startswith('LLS_Basic')][0]
        basic_light_layer = find_view_layer(basic_light_collection, bpy.context.view_layer.layer_collection)

        advanced_light_collection = [c for c in light_collection.children if c.name.startswith('LLS_Advanced')][0]
        advanced_light_layer = find_view_layer(advanced_light_collection, bpy.context.view_layer.layer_collection)

        if basic_light_layer.exclude + advanced_light_layer.exclude != 1:
            advanced_light_layer.exclude = False
            basic_light_layer.exclude = True

        if not basic_light_layer.exclude:
            light_object = basic_light_collection.objects[0]
        elif not advanced_light_layer.exclude:
            light_object = advanced_light_collection.objects[0]


        if light_object.name in bpy.context.view_layer.objects:
            bpy.context.view_layer.objects.active = light_object
            light_object.select_set(True)

        if modal.running_modals:
            light_icon = [l for l in LightImage.lights if l._lls_handle == light_object.parent][0]
            send_light_to_top(light_icon)
    except IndexError:
        print("Malformed light. Trying to fix.")
        light = salvage_data(light_collection)
        light_root = light_handle.parent.parent
        profile_collection = light_root.parent.users_collection[0]
        family_obs = family(light_root)
        bpy.ops.object.delete({"selected_objects": list(family_obs)}, use_global=True)
        bpy.data.collections.remove(light_collection)
        light_from_dict(light, profile_collection)


def update_light_list_set(context, profile_idx=None):
    '''Update light list set. Use when the light list needs to be synced with real object hierarchy. '''
    props = context.scene.LLStudio
    # lls_collection, profile_collection = llscol_profilecol(context)
    lls_collection = get_lls_collection(context)
    profile_idx = props.profile_list_index if profile_idx==None else profile_idx
    profile_collection = bpy.data.objects[props.profile_list[profile_idx].empty_name].users_collection[0]
    if profile_collection is not None and (props.profile_list[profile_idx].enabled or not props.profile_multimode):
        props.light_list.clear()

        lls_lights = set(profile_collection.children)
        
        lights = [m for col in lls_lights for m in col.objects if m.name.startswith("LLS_LIGHT_HANDLE")]
        lights.sort(key= lambda m: m.LLStudio.order_index)
        for i, lls_handle in enumerate(lights):
            lls_handle.LLStudio.order_index = i
            ll = props.light_list.add()
            ll.handle_name = lls_handle.name
            ll.name = lls_handle.LLStudio.light_name if lls_handle.LLStudio.light_name else f"Light {lls_handle.LLStudio.order_index}"

            view_layer = find_view_layer(lls_handle.users_collection[0], context.view_layer.layer_collection)
            visible_lights = [c for c in lls_handle.children if c.visible_get()]
            if len(visible_lights) == 1 and not view_layer.exclude:
                light_object = visible_lights[0]
                real_light_type = 'ADVANCED' if light_object.type == 'MESH' else 'BASIC'
                if real_light_type != lls_handle.LLStudio.type:
                    lls_handle.LLStudio.type = lls_handle.LLStudio.type
            else:
                # check if view_layer exists because profile can be muted
                if view_layer and not view_layer.exclude:
                    lls_handle.LLStudio.type = lls_handle.LLStudio.type
                elif view_layer:
                    for vl in view_layer.children:
                        vl.exclude = True
    else:
        props.light_list.clear()

class LLS_OT_MuteToggle(bpy.types.Operator):
    bl_idname = "light_studio.mute_toggle"
    bl_label = "Mute Light"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    index: IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and context.scene.LLStudio.initialized

    def execute(self, context):
        props = context.scene.LLStudio
        handle_name = props.light_list[self.index].handle_name
        light_handle = context.scene.objects[handle_name]
        light_collection = get_collection(light_handle)

        view_layer = find_view_layer(light_collection, context.view_layer.layer_collection)
        view_layer.exclude = not view_layer.exclude

        if not view_layer.exclude:
            light_handle.LLStudio.type = light_handle.LLStudio.type
        return {"FINISHED"}

class LLS_OT_Isolate(bpy.types.Operator):
    bl_idname = "light_studio.isolate"
    bl_label = "Isolate Light"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    index: IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and context.scene.LLStudio.initialized

    def execute(self, context):
        props = context.scene.LLStudio
        handle_name = props.light_list[self.index].handle_name
        light_handle = context.scene.objects[handle_name]
        light_collection = get_collection(light_handle)
        view_layer = find_view_layer(light_collection, context.view_layer.layer_collection)
        
        view_layers=[]
        excluded=0
        for li in props.light_list:
            lls_handle = context.scene.objects[li.handle_name]
            light_collection = get_collection(lls_handle)

            vl = find_view_layer(light_collection, context.view_layer.layer_collection)
            view_layers.append(vl)
            excluded += vl.exclude
        # print([v.name for v in view_layers])

        if not view_layer.exclude and excluded == len(view_layers)-1:
            for v in view_layers:
                v.exclude = False
                lls_handle = v.children[0].collection.objects[0].parent
                lls_handle.LLStudio.type = lls_handle.LLStudio.type
        else:
            for v in view_layers:
                if not v.exclude:
                    # Do not set exclude=True twice because it propagates to children.
                    v.exclude = True
            view_layer.exclude = False
            light_handle.LLStudio.type = light_handle.LLStudio.type

        return {"FINISHED"}

class LLS_OT_LightListMoveItem(bpy.types.Operator):
    bl_idname = "lls_list.move_light"
    bl_label = "Move Light"
    bl_options = {"INTERNAL"}

    direction: bpy.props.EnumProperty(
                items=(
                    ('UP', 'Up', ""),
                    ('DOWN', 'Down', ""),))

    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list. """
        return len(context.scene.LLStudio.light_list)

    def execute(self, context):
        props = context.scene.LLStudio
        list = props.light_list
        index = props.light_list_index

        if self.direction == 'DOWN':
            neighbor = index + 1
            list.move(index,neighbor)
        elif self.direction == 'UP':
            neighbor = index - 1
            list.move(neighbor, index)
        else:
            return{'CANCELLED'}

        for i, e in enumerate(list):
            if e.handle_name in bpy.data.objects:
                bpy.data.objects[e.handle_name].LLStudio.order_index = i

        return{'FINISHED'}

class LIST_OT_LightListCopyItem(bpy.types.Operator):

    bl_idname = "lls_list.copy_light"
    bl_label = "Copy Light"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        light = context.active_object
        props = context.scene.LLStudio
        if not (context.area.type == 'VIEW_3D' and \
               context.mode == 'OBJECT' and \
               props.initialized and \
               light and \
               light.name.startswith('LLS_LIGHT_')):
            return False
        
        if props.profile_multimode:
            profile = findLightProfileObject(light)
            list_profile = props.profile_list[props.profile_list_index]
            return list_profile.enabled and profile and profile.name == list_profile.empty_name
        else:
            return True

    def execute(self, context):
        props = context.scene.LLStudio

        lls_collection, profile_collection = llscol_profilecol(context)
        lls_handle = context.object.parent
        lcol = [c for c in lls_handle.users_collection if c.name.startswith('LLS_Light')]
        
        if not lcol:
            return{'CANCELLED'}
        
        lcol = lcol[0]
        light_copy = duplicate_collection(lcol, profile_collection)
        lls_handle_copy = [lm for lm in light_copy.objects if lm.name.startswith('LLS_LIGHT_HANDLE')][0] # original light mesh exists so no checks necessary
        lls_handle_copy.LLStudio.light_name = lls_handle.LLStudio.light_name if lls_handle.LLStudio.light_name else f"Light {lls_handle.LLStudio.order_index}"
        lls_handle_copy.LLStudio.light_name += " Copy"
        lls_handle_copy.LLStudio.order_index += 1

        # place copied profile next to source profile
        for e in props.light_list[lls_handle.LLStudio.order_index + 1 : ]:
            bpy.data.objects[e.handle_name].LLStudio.order_index += 1

        update_light_list_set(context)
        
        light_object = [obj for obj in lls_handle_copy.children if obj.visible_get()][0]
        bpy.context.view_layer.objects.active = light_object
        light_object.select_set(True)

        if modal.panel_global:
            update_light_sets(modal.panel_global, context, always=True)
            light_icon = [l for l in LightImage.lights if l._lls_handle == lls_handle][0]
            send_light_to_top(light_icon)

        return{'FINISHED'}

from bpy.app.handlers import persistent
@persistent
def load_post(scene):
    context = bpy.context
    props = bpy.context.scene.LLStudio
    
    if not props.initialized:
        return

    lls_collection, profile_collection = llscol_profilecol(context)

    if profile_collection is None:
        return

    # props.light_list.clear()

    lls_lights = set(profile_collection.children)
    
    lights = [m for col in lls_lights for m in col.objects if m.name.startswith("LLS_LIGHT_MESH")]
    for i, lls_mesh in enumerate(lights):
        convert_old_light(lls_mesh, profile_collection)
    update_light_list_set(bpy.context)


    # Also check new lights if they are up to date
    roots = [o for o in bpy.context.scene.objects if o.name.startswith("LEOMOON_LIGHT_STUDIO")]
    for root in roots:
        all_elems = family(root)
        matching_names = []
        for elem in all_elems:
            matches = ['LLS_LIGHT_MESH']
            if any(x in elem.name for x in matches):
                matching_names.append(elem.name)
    
    # print(matching_names)
    for name in matching_names:
        elem = bpy.data.objects[name]
        try:
            salvage_data(get_collection(elem.parent), only_validate=True)
        except:
            print("Recreate light:", elem.name)
            llscol, profilecol = llscol_profilecol(context)
            convert_old_light(elem.parent, profilecol)
            update_light_list_set(bpy.context)


def register():
    bpy.app.handlers.load_post.append(load_post)

def unregister():
    bpy.app.handlers.load_post.remove(load_post)