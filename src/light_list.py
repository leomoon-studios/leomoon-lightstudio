import bpy
from bpy.props import BoolProperty, StringProperty, PointerProperty, FloatProperty, EnumProperty, IntProperty
import os, sys, subprocess
from . common import *
from itertools import chain
from . operators.modal import close_control_panel

_ = os.sep

class LightListItem(bpy.types.PropertyGroup):
    """ Group of properties representing an item in the list """
    def update_name(self, context):
        bpy.data.objects[self.mesh_name].LLStudio.light_name = self.name

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
    bpy.context.view_layer.objects.active = ob   # Make the cube the active object 
    ob.select_set(True)

def update_light_list_set(context):
    '''Update light list set. Use when the light list needs to be synced with real object hierarchy. '''
    props = context.scene.LLStudio
    lls_collection, profile_collection = llscol_profilecol(context)
    if profile_collection is not None:
        props.light_list.clear()
        lls_lights = set(profile_collection.children)
        for col in lls_lights:
            ll = props.light_list.add()
            lls_mesh = [m for m in col.objects if m.name.startswith("LLS_LIGHT_MESH")]
            if not lls_mesh:
                bpy.ops.object.delete({"selected_objects": col.objects}, use_global=True)
                bpy.data.collections.remove(col)
                return update_light_list_set(context)

            lls_mesh = lls_mesh[0]
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