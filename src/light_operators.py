import bpy
from bpy.props import BoolProperty, PointerProperty, FloatProperty, CollectionProperty, IntProperty, StringProperty
from . window_operations import splitV3DtoBLS
from . light_profiles import ListItem, update_list_index
from . common import *
import os

_ = os.sep

from extensions_framework import util as efutil
from . import bl_info
class Blender_Light_Studio_Properties(bpy.types.PropertyGroup):
    initialized = BoolProperty(default = False)
            
    def get_light_hidden(self):
        return getLightMesh().hide_render
    
    def set_light_hidden(self, context):
        light = getLightMesh()
        light.hide_render = context
        light.hide = context
        bpy.context.scene.frame_current = bpy.context.scene.frame_current # refresh hack
        refreshMaterials()
    
    light_muted = BoolProperty(name="Mute Light", default=False, set=set_light_hidden, get=get_light_hidden)
    
    def get_selection_overriden(self):
        from . selectOperator import addon_keymaps
        keylen = bool(len(addon_keymaps))
        #print(addon_keymaps)
        
    
        if not (hasattr(bpy, 'bls_selection_override_left') and hasattr(bpy, 'bls_selection_override_right')):
            bpy.bls_selection_override_left = efutil.find_config_value(bl_info['name'], 'defaults', 'selection_override_left', False)
            bpy.bls_selection_override_right = efutil.find_config_value(bl_info['name'], 'defaults', 'selection_override_right', True)
                        
        selection_override = bpy.bls_selection_override_right if bpy.context.user_preferences.inputs.select_mouse == 'RIGHT' else bpy.bls_selection_override_left
            
        if keylen != selection_override:
            from . selectOperator import add_shortkeys, remove_shortkeys
            if selection_override:
                add_shortkeys()
            else:
                remove_shortkeys()
        return selection_override
    
    def set_selection_overriden(self, context):
        from . selectOperator import add_shortkeys, remove_shortkeys
        if context:
            add_shortkeys()
        else:
            remove_shortkeys()
        
        if bpy.context.user_preferences.inputs.select_mouse == 'RIGHT':
            bpy.bls_selection_override_right = context
            efutil.write_config_value(bl_info['name'], 'defaults', 'selection_override_right', context)
        else:
            bpy.bls_selection_override_left = context
            efutil.write_config_value(bl_info['name'], 'defaults', 'selection_override_left', context)
        
            
    selection_overriden = BoolProperty(
        name="Override Selection",
        default = True,
        set=set_selection_overriden,
        get=get_selection_overriden
    )
    
    
    ''' Profile List '''
    profile_list = CollectionProperty(type = ListItem)
    list_index = IntProperty(name = "Index for profile_list", default = 0, update=update_list_index)
    last_empty = StringProperty(name="Name of last Empty holding profile", default="")
    

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
        
        bpy.ops.wm.append(filepath=_+'BLS.blend'+_+'Object'+_,
        directory=os.path.join(dir,"BLS.blend"+_+"Object"+_),
        filename="BLENDER_LIGHT_STUDIO",
        active_layer=False)

        bpy.ops.wm.append(filepath=_+'BLS.blend'+_+'Object'+_,
        directory=os.path.join(dir,"BLS.blend"+_+"Object"+_),
        filename="BLS_PANEL",
        active_layer=False)
        
        cpanel = [ob for ob in bpy.context.scene.objects if ob.name.startswith('BLS_PANEL')][0]
        cpanel.parent = [ob for ob in bpy.context.scene.objects if ob.name.startswith('BLENDER_LIGHT_STUDIO')][0]

        bpy.ops.bls_list.new_profile()
        
        context.scene.BLStudio.initialized = True
        
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
            scene.objects.unlink(ob)
            for gr in ob.users_group:
                gr.objects.unlink(ob)
            ob.user_clear()
            ob.use_fake_user = False
            bpy.data.objects.remove(ob)
            
        
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
        bls = [ob for ob in bpy.context.scene.objects if ob.name.startswith('BLENDER_LIGHT_STUDIO')][0]
    
        # before
        A = set(bpy.data.groups[:])
        A_actions = set(bpy.data.actions[:]) # remove bugged actions (Blender 2.78 bug)
        
        bpy.ops.wm.append(filepath=_+'BLS.blend'+_+'Group'+_,
        directory=os.path.join(dir,"BLS.blend"+_+"Group"+_),
        filename="BLS_Light",
        active_layer=False)
        
        if bpy.data.actions.find("BLS_ROT_X") == -1:
            bpy.ops.wm.append(filepath=_+'BLS.blend'+_+'Action'+_,
            directory=os.path.join(dir,"BLS.blend"+_+"Action"+_),
            filename="BLS_ROT_X",
            active_layer=False)

        if bpy.data.actions.find("BLS_ROT_Z") == -1:
            bpy.ops.wm.append(filepath=_+'BLS.blend'+_+'Action'+_,
            directory=os.path.join(dir,"BLS.blend"+_+"Action"+_),
            filename="BLS_ROT_Z",
            active_layer=False)
            

        #################
        # maybe later
        '''
        filepath = os.path.join(dir,"BLS.blend") #os.path.join(os.sep, "BLS.blend")
        # load a single scene we know the name of.
        with bpy.data.libraries.load(filepath) as (data_from, data_to):
            data_to.groups = ["BLS_Light"]
            
        for group in data_to.groups:
            if group is not None:
                print(group.name)
                bpy.ops.object.group_link(group=group.name)
        '''
        #################
        
        # after operation
        B = set(bpy.data.groups[:])

        # whats the difference
        new_objects = (A ^ B).pop().objects
        
        for ob in new_objects:
            print(ob)
            ob.use_fake_user = True
        
        lightGrp = [l for l in new_objects if l.name.startswith('BLS_LIGHT_GRP')][0]
        profile = [ob for ob in bpy.context.scene.objects if ob and ob.name.startswith('BLS_PROFILE') and isFamily(ob)][0]
        handle = [ob for ob in profile.children if ob.name.startswith('BLS_HANDLE')][0]
        lightGrp.parent = profile
        
        bpy.ops.object.select_all(action='DESELECT')
        light = [p for p in new_objects if p.name.startswith('BLS_LIGHT_MESH')][0]
        light.select = True
        panel = [p for p in new_objects if p.name.startswith('BLS_CONTROLLER')][0]
        panel.select = True
        context.scene.objects.active = panel
        
        ##### Blender 2.78 workaround. Constraints cannot be appended
        c = light.constraints.new('COPY_ROTATION')
        c.target = panel
        c.use_x = False
        c.use_y = False
        c.owner_space = 'LOCAL'
        c.use_z = True
        c.invert_z = True
        
        c = light.constraints.new('TRANSFORM')
        c.target = panel
        c.use_motion_extrapolate = True
        c.map_from = 'SCALE'
        c.from_min_x_scale = 0.1
        c.from_max_x_scale = 20
        c.from_min_y_scale = 0.1
        c.from_max_y_scale = 20
        c.from_min_z_scale = 0.1
        c.from_max_z_scale = 20
        
        c.map_to_x_from = 'Z'
        c.map_to_y_from = 'X'
        c.map_to_z_from = 'Y'
        
        c.map_to = 'SCALE'
        c.to_min_x_scale = 0.1
        c.to_max_x_scale = 20
        c.to_min_y_scale = 0.1
        c.to_max_y_scale = 20
        c.to_min_z_scale = 0.1
        c.to_max_z_scale = 20
        
        ##
        c = panel.constraints.new('LIMIT_LOCATION')
        c.use_min_x = True
        c.min_x = -2
        c.use_max_x = True
        c.max_x = 2
        
        c.use_min_y = True
        c.min_y = -1
        c.use_max_y = True
        c.max_y = 1
        
        c = panel.constraints.new('LIMIT_SCALE')
        c.use_min_x = True
        c.min_x = 0.1
        c.use_min_y = True
        c.min_y = 0.1
        c.use_min_z = True
        c.min_z = 0.1
        
        ##
        armature1 = [a for a in new_objects if a.name.startswith("BLS_Armature")][0]
        armature2 = [a for a in new_objects if a.name.startswith("BLS_Armature2")][0]
        
        c = armature1.constraints.new('ACTION')
        c.target = panel
        c.action = bpy.data.actions["BLS_ROT_Z"]
        c.min = -2
        c.max = 2
        c.frame_start = 1
        c.frame_end = 500
        
        c = armature2.constraints.new('ACTION')
        c.target = panel
        c.action = bpy.data.actions["BLS_ROT_X"]
        c.transform_channel = 'LOCATION_Y'
        c.min = -1
        c.max = 1
        c.frame_start = 1
        c.frame_end = 500
        #####
        
        c = light.constraints.new('COPY_LOCATION')
        c.target = handle
        c.use_x = True
        c.use_y = True
        c.use_z = True
        c.use_offset = True
        bpy.context.scene.frame_current = bpy.context.scene.frame_current # refresh hack
        refreshMaterials()
                
        return {"FINISHED"}
    
class DeleteBSLight(bpy.types.Operator):
    bl_idname = "scene.delete_blender_studio_light"
    bl_label = "Delete BLS Light"
    bl_description = "Delete selected Light from Studio"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        light = context.scene.objects.active
        return context.area.type == 'VIEW_3D' and \
               context.mode == 'OBJECT' and \
               context.scene.BLStudio.initialized and \
               light and \
               light.name.startswith('BLS_') and \
               not (light.name.startswith('BLS_PANEL') or light.name.startswith('BLS_PROFILE') or light.name.startswith('BLS_LIGHT_GRP'))

    def execute(self, context):
        scene = context.scene
        oldlaysArea = context.area.spaces[0].layers[:]
        oldlaysScene = context.scene.layers[:]
        context.area.spaces[0].layers = [True]*20
        context.scene.layers = [True]*20
        
        light = bpy.context.scene.objects.active
        
        
        lightGrp = findLightGrp(light)
        if lightGrp == None:
            if light.parent and light.parent.name.startswith('BLS_PROFILE'):
                light.select = False
                self.report({'WARNING'}, "Delete Profile in order to delete Handle")
                return {"CANCELLED"}
            else:
                scene.objects.unlink(light)
                return {"FINISHED"}
            
        ending = lightGrp.name.split('.')[1]
        
        #obsToRemove = [ob for ob in scene.objects if not ob.name.startswith('BLS_PROFILE.') and ob.name.endswith(ending) and isFamily(ob)]
        #print(obsToRemove)
        for ob in family(lightGrp):
            scene.objects.unlink(ob)
            for gr in ob.users_group:
                gr.objects.unlink(ob)
            ob.user_clear()
            ob.use_fake_user = False
            bpy.data.objects.remove(ob)
        
        context.area.spaces[0].layers = oldlaysArea
        context.scene.layers = oldlaysScene
                
        return {"FINISHED"}
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="OK?")
    
class PrepareBSLV3D(bpy.types.Operator):
    bl_idname = "scene.prepare_blender_studio_light"
    bl_label = "Prepare Layout"
    bl_description = "Split current Viewport for easier Studio usage."
    bl_options = {"REGISTER"}
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and context.scene.BLStudio.initialized
    
    def execute(self, context):
        splitV3DtoBLS(context)
        context.scene.render.engine="CYCLES"
        return {"FINISHED"}
    
class BSL_MuteOtherLights(bpy.types.Operator):
    bl_idname = "object.mute_other_lights"
    bl_label = "Show Only This Light"
    bl_description = "Show only this light."
    bl_options = {"INTERNAL", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and context.scene.BLStudio.initialized \
            and context.scene.objects.active and (context.scene.objects.active.name.startswith('BLS_CONTROLLER') or context.scene.objects.active.name.startswith('BLS_LIGHT_MESH'))
    
    def execute(self, context):
        obs = context.scene.objects
        lightGrp = obs.active
        light_no = lightGrp.name.split('.')[1]
    
        for light in (ob for ob in obs if ob.name.startswith('BLS_LIGHT_MESH') and isFamily(ob)):
            if light.name[-3:] == light_no:
                light.hide_render = False
                light.hide = False
            else:
                light.hide_render = True
                light.hide = True
                
        context.scene.frame_current = context.scene.frame_current # refresh hack
        refreshMaterials()
    
        return {"FINISHED"}
    
class BSL_ShowAllLights(bpy.types.Operator):
    bl_idname = "object.show_all_lights"
    bl_label = "Show All Lights"
    bl_description = "Show all lights."
    bl_options = {"INTERNAL", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and context.scene.BLStudio.initialized
    
    def execute(self, context):
        obs = context.scene.objects
        for light in (ob for ob in obs if ob.name.startswith('BLS_LIGHT_MESH') and isFamily(ob)):
            light.hide_render = False
            light.hide = False
                
        context.scene.frame_current = context.scene.frame_current # refresh hack
        refreshMaterials()
    
        return {"FINISHED"}
        