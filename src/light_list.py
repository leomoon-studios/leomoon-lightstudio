import bpy
from bpy.props import BoolProperty, StringProperty, PointerProperty, FloatProperty, EnumProperty, IntProperty
import os, sys, subprocess
from . common import *
from itertools import chain
from . operators import modal
from . operators.modal import close_control_panel, update_light_sets
from . operators.modal_utils import send_light_to_top, LightImage

_ = os.sep

class LightListItem(bpy.types.PropertyGroup):
    """ Group of properties representing an item in the list """
    def update_name(self, context):
        name = self.name
        if self.name == '':
            name = self.mesh_name
            self.name = name
        bpy.data.objects[self.mesh_name].LLStudio.light_name = name

    name: StringProperty(
            name="Profile Name",
            default="Untitled",
            update=update_name)

    mesh_name: StringProperty(
            description="",
            default="")

class LLS_UL_LightList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        custom_icon = 'OUTLINER_OB_LIGHT' if index == context.scene.LLStudio.list_index else 'LIGHT'

        if item.mesh_name in context.scene.objects:
            # Make sure your code supports all 3 layout types
            if self.layout_type in {'DEFAULT', 'COMPACT'}:
                layout.prop(item, 'name', text='', emboss=False, translate=False)

                mesh_object = context.scene.objects[item.mesh_name]
                mesh_collection = get_collection(mesh_object)

                view_layer = find_view_layer(mesh_collection, context.view_layer.layer_collection)
                icon = 'LIGHT' if view_layer.exclude else 'OUTLINER_OB_LIGHT'
                layout.operator('light_studio.mute_toggle', emboss=False, icon=icon, text="").index = index

                
                props = context.scene.LLStudio
                excluded=0
                for li in props.light_list:
                    if not li.mesh_name in context.scene.objects:
                        continue
                    mesh_object = context.scene.objects[li.mesh_name]
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
            if li.mesh_name == ob.name:
                return i
    return -1

def set_list_index(self, index):
    selected_light = self.light_list[index]
    ob = bpy.context.scene.objects[selected_light.mesh_name]       # Get the object
    bpy.ops.object.select_all(action='DESELECT') # Deselect all objects
    if ob.name in bpy.context.view_layer.objects:
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)

    if modal.running_modals:
        light_icon = [l for l in LightImage.lights if l._lls_mesh == ob][0]
        send_light_to_top(light_icon)

def update_light_list_set(context):
    '''Update light list set. Use when the light list needs to be synced with real object hierarchy. '''
    props = context.scene.LLStudio
    lls_collection, profile_collection = llscol_profilecol(context)
    if profile_collection is not None:
        props.light_list.clear()

        lls_lights = set(profile_collection.children)
        lights = [m for col in lls_lights for m in col.objects if m.name.startswith("LLS_LIGHT_MESH")]
        lights.sort(key= lambda m: m.LLStudio.order_index)
        for i, lls_mesh in enumerate(lights):
            lls_mesh.LLStudio.order_index = i
            ll = props.light_list.add()
            ll.mesh_name = lls_mesh.name
            ll.name = lls_mesh.LLStudio.light_name if lls_mesh.LLStudio.light_name else lls_mesh.name

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
        mesh_name = props.light_list[self.index].mesh_name
        mesh_object = context.scene.objects[mesh_name]
        mesh_collection = get_collection(mesh_object)

        view_layer = find_view_layer(mesh_collection, context.view_layer.layer_collection)
        view_layer.exclude = not view_layer.exclude
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
        mesh_name = props.light_list[self.index].mesh_name
        mesh_object = context.scene.objects[mesh_name]
        mesh_collection = get_collection(mesh_object)
        view_layer = find_view_layer(mesh_collection, context.view_layer.layer_collection)
        
        view_layers=[]
        excluded=0
        for li in props.light_list:
            mesh_object = context.scene.objects[li.mesh_name]
            mesh_collection = get_collection(mesh_object)

            vl = find_view_layer(mesh_collection, context.view_layer.layer_collection)
            view_layers.append(vl)
            excluded += vl.exclude

        if not view_layer.exclude and excluded == len(view_layers)-1:
            for v in view_layers:
                v.exclude = False
        else:
            for v in view_layers:
                v.exclude = True
            view_layer.exclude = False

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
            if e.mesh_name in bpy.data.objects:
                bpy.data.objects[e.mesh_name].LLStudio.order_index = i

        return{'FINISHED'}

class LIST_OT_LightListCopyItem(bpy.types.Operator):

    bl_idname = "lls_list.copy_light"
    bl_label = "Copy Light"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        light = context.active_object
        return context.area.type == 'VIEW_3D' and \
               context.mode == 'OBJECT' and \
               context.scene.LLStudio.initialized and \
               light and \
               light.name.startswith('LLS_LIGHT')

    def execute(self, context):
        props = context.scene.LLStudio
        list = props.profile_list


        lls_collection, profile_collection = llscol_profilecol(context)
        lls_mesh = context.object
        lcol = [c for c in lls_mesh.users_collection if c.name.startswith('LLS_Light')]
        
        if not lcol:
            return{'CANCELLED'}
        
        lcol = lcol[0]
        light_copy = duplicate_collection(lcol, profile_collection)
        lls_mesh_copy = [lm for lm in light_copy.objects if lm.name.startswith('LLS_LIGHT_MESH')][0] # original light mesh exists so no checks necessary
        lls_mesh_copy.LLStudio.light_name += " Copy"
        lls_mesh_copy.LLStudio.order_index += 1

        # place copied profile next to source profile
        for e in props.light_list[lls_mesh.LLStudio.order_index + 1 : ]:
            bpy.data.objects[e.mesh_name].LLStudio.order_index += 1

        update_light_list_set(context)

        if modal.panel_global:
            update_light_sets(modal.panel_global, context, always=True)
            light_icon = [l for l in LightImage.lights if l._lls_mesh == lls_mesh][0]
            send_light_to_top(light_icon)

        return{'FINISHED'}