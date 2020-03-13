import bpy
from bpy.props import BoolProperty, PointerProperty, FloatProperty, CollectionProperty, IntProperty, StringProperty
from . light_profiles import ListItem, update_list_index
from . common import *
import os
from . import operators

_ = os.sep

from . extensions_framework import util as efutil
from . import bl_info
    
class Blender_Light_Studio_Properties(bpy.types.PropertyGroup):
    initialized: BoolProperty(default = False)    
    
    ''' Profile List '''
    profile_list: CollectionProperty(type = ListItem)
    list_index: IntProperty(name = "Index for profile_list", default = 0, update=update_list_index)
    last_empty: StringProperty(name="Name of last Empty holding profile", default="")
    

class CreateBlenderLightStudio(bpy.types.Operator):
    bl_idname = "scene.create_blender_light_studio"
    bl_label = "Create Light Studio"
    bl_description = "Append Blender Light Studio to current scene"
    bl_options = {"REGISTER"}
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and not context.scene.BLStudio.initialized
    
    def execute(self, context):
        script_file = os.path.realpath(__file__)
        dir = os.path.dirname(script_file)

        bpy.ops.wm.append(filepath=_+'BLS3.blend'+_+'Collection'+_,
        directory=os.path.join(dir,"BLS3.blend"+_+"Collection"+_),
        filename="BLS",
        active_collection=False)

        bpy.ops.bls_list.new_profile()
        
        context.scene.BLStudio.initialized = True

        bpy.context.scene.render.engine = 'CYCLES'

        # add the first light
        # bpy.ops.object.select_all(action='DESELECT')
        # bpy.ops.scene.add_blender_studio_light()
        
        return {"FINISHED"}
  
class DeleteBlenderLightStudio(bpy.types.Operator):
    bl_idname = "scene.delete_blender_light_studio"
    bl_label = "Delete Studio"
    bl_description = "Delete Blender Light Studio from current scene"
    bl_options = {"REGISTER"}
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and context.scene.BLStudio.initialized
    
    def execute(self, context):
        scene = context.scene
        scene.BLStudio.initialized = False
        
        ''' for each profile from this scene: delete objects then remove from list '''
        while len(context.scene.BLStudio.profile_list):
            bpy.ops.bls_list.delete_profile()
            
        obsToRemove = [ob for ob in scene.objects if isFamily(ob)]
        for ob in obsToRemove:
            for c in ob.users_collection:
                c.objects.unlink(ob)
            ob.user_clear()
            ob.use_fake_user = False
            bpy.data.objects.remove(ob)
            
        context.scene.collection.children.unlink(get_bls_collection(context))
        
        return {"FINISHED"}
     
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Deleting Studio is irreversible!")
        col.label(text="Your lighting setup will be lost.")

class AddBSLight(bpy.types.Operator):
    bl_idname = "scene.add_blender_studio_light"
    bl_label = "Add Studio Light"
    bl_description = "Add Light to Studio"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and context.scene.BLStudio.initialized
    
    def execute(self, context):
        script_file = os.path.realpath(__file__)
        dir = os.path.dirname(script_file)
        
        scene = context.scene
        bls_collection, profile_collection, profile, handle = blscol_profilecol_profile_handle(context)

        filepath = os.path.join(dir,"BLS3.blend")
        # load a single scene we know the name of.
        with bpy.data.libraries.load(filepath) as (data_from, data_to):
            data_to.collections = ["BLS_Light"]
            
        for collection in data_to.collections:
            if collection is not None:
                profile_collection.children.link(collection)
                new_objects = collection.objects
                for ob in new_objects:
                    ob.use_fake_user = True
                
                blslight = [l for l in new_objects if l.name.startswith('BLS_LIGHT')][0]
                blslight.parent = profile 
                
                bpy.ops.object.select_all(action='DESELECT')
                light = [p for p in new_objects if p.name.startswith('BLS_LIGHT_MESH')][0]
                light.select_set(True)
                context.view_layer.objects.active = light
        
        #####
        
        c = light.constraints.new('COPY_LOCATION')
        c.target = handle
        c.use_x = True
        c.use_y = True
        c.use_z = True
        c.use_offset = True
        # scene.frame_current = bpy.context.scene.frame_current # refresh hack
        # refreshMaterials()
        
        operators.update()
        return {"FINISHED"}
    
class DeleteBSLight(bpy.types.Operator):
    bl_idname = "scene.delete_blender_studio_light"
    bl_label = "Delete BLS Light"
    bl_description = "Delete selected Light from Studio"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        light = context.active_object
        return context.area.type == 'VIEW_3D' and \
               context.mode == 'OBJECT' and \
               context.scene.BLStudio.initialized and \
               light and \
               light.name.startswith('BLS_LIGHT') and \
               not light.name.startswith('BLS_PROFILE')

    def execute(self, context):
        scene = context.scene
        light = context.object

        for collection in light.users_collection:
            if collection.name.startswith('BLS_Light'):
                bpy.ops.object.delete({"selected_objects": collection.objects}, use_global=True)
                bpy.data.collections.remove(collection)
                
        operators.update()
        return {"FINISHED"}
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="OK?")

class BUILTIN_KSI_LightStudio(bpy.types.KeyingSetInfo):
    bl_label = "LightStudio KeyingSet"

    # poll - test for whether Keying Set can be used at all
    def poll(ksi, context):
        return context.active_object or context.selected_objects and context.scene.BLStudio.initialized

    # iterator - go over all relevant data, calling generate()
    def iterator(ksi, context, ks):
        for ob in (l for l in context.selected_objects if l.name.startswith("BLS_LIGHT")):
            ksi.generate(context, ks, ob)

    # generator - populate Keying Set with property paths to use
    def generate(ksi, context, ks, data):
        id_block = data.id_data

        bls_collection = get_collection(id_block)
        light_mesh = [m for m in bls_collection.objects if m.name.startswith("BLS_LIGHT_MESH")][0]
        bls_actuator = light_mesh.parent
        
        ks.paths.add(light_mesh, "location", index=0, group_method='KEYINGSET')
        ks.paths.add(light_mesh, "rotation_euler", index=0, group_method='KEYINGSET')
        ks.paths.add(light_mesh, "scale", group_method='KEYINGSET')
        ks.paths.add(bls_actuator, "rotation_euler", group_method='KEYINGSET')