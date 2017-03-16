import bpy
from bpy.props import StringProperty, PointerProperty, FloatProperty, EnumProperty
import os
from . common import isFamily, family, findLightGrp, getLightHandle
from itertools import chain

_ = os.sep

class ListItem(bpy.types.PropertyGroup):
    """ Group of properties representing an item in the list """
    def update_name(self, context):
        print("{} : {}".format(repr(self.name), repr(context)))
                
    name = StringProperty(
            name="Profile Name",
            default="Untitled")

    empty_name = StringProperty(
            name="Name of Empty holding profile",
            description="",
            default="")
            
class BLS_UL_List(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        custom_icon = 'OUTLINER_OB_LAMP' if index == context.scene.BLStudio.list_index else 'LAMP'

        # Make sure your code supports all 3 layout types
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, 'name', text='', icon = custom_icon, emboss=False, translate=False)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label("", icon = custom_icon)
            
            
class LIST_OT_NewItem(bpy.types.Operator):
    """ Add a new profile to the list """

    bl_idname = "bls_list.new_profile"
    bl_label = "Add a new Profile"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        props = context.scene.BLStudio
        item = props.profile_list.add()
        
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
        bpy.ops.wm.append(filepath=_+'BLS.blend'+_+'Object'+_,
        directory=os.path.join(dir,"BLS.blend"+_+"Object"+_),
        filename="BLS_PROFILE.000",
        active_layer=False)
        
        # after operation
        B = set(bpy.data.objects[:])

        # whats the difference
        profile = (A ^ B).pop()
        
        profile.parent = [ob for ob in bpy.context.scene.objects if ob.name.startswith('BLENDER_LIGHT_STUDIO')][0]
        profile.use_fake_user = True
        
        item.empty_name = profile.name
        
        bpy.ops.object.empty_add(type='PLAIN_AXES', radius=1, view_align=False, location=(0, 0, 0), layers=(True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False))
        handle = context.active_object
        handle.parent = profile
        handle.name = "BLS_HANDLE"
        handle.protected = True
        handle['last_layers'] = handle.layers[:]
        handle.empty_draw_type = 'SPHERE'
        
        #if len([prof for prof in profile.parent.children if prof.name.startswith('BLS_PROFILE.')]) > 1:
        if len([prof for prof in context.scene.objects if prof.name.startswith('BLS_PROFILE.') and isFamily(prof)]) > 1:
            #profile already exists
            context.scene.objects.unlink(profile)
            context.scene.objects.unlink(handle)
        else:
            #init last_empty for first profile
            props.last_empty = profile.name
        

        return{'FINISHED'}

class LIST_OT_DeleteItem(bpy.types.Operator):
    """ Delete the selected profile from the list """
 
    bl_idname = "bls_list.delete_profile"
    bl_label = "Deletes an profile"
    bl_options = {"INTERNAL"}
 
    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list """
        return len(context.scene.BLStudio.profile_list)
 
    def execute(self, context):
        props = context.scene.BLStudio
        list = props.profile_list
        index = props.list_index
 
        list.remove(index)
        
        ''' Delete/Switch Hierarchy stuff '''
        #delete objects from current profile           
        obsToRemove = family(context.scene.objects[props.last_empty])
        for ob in obsToRemove:
            context.scene.objects.unlink(ob)
            for gr in ob.users_group:
                gr.objects.unlink(ob)
            ob.user_clear()
            ob.use_fake_user = False
            bpy.data.objects.remove(ob)
        
        # update index
        if index > 0:
            index = index - 1
        props.list_index = index
 
        return{'FINISHED'}
    

class LIST_OT_CopyItem(bpy.types.Operator):
    """ Copy an item in the list """

    bl_idname = "bls_list.copy_profile"
    bl_label = "Copy profile"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list. """
        return len(context.scene.BLStudio.profile_list)

    def execute(self, context):
        props = context.scene.BLStudio
        list = props.profile_list
        index = props.list_index
        
        scene = context.scene
        
        # all objects on all layers visible
        oldlaysArea = context.area.spaces[0].layers[:]
        oldlaysScene = context.scene.layers[:]
        context.area.spaces[0].layers = [True]*20
        context.scene.layers = [True]*20
        
        obsToCopy = family(context.scene.objects[props.last_empty])
        
        for ob in context.selected_objects: ob.select = False
        for ob in obsToCopy:
            if ob.name.startswith('BLS_PROFILE.'): continue
            ob.hide_select = False
            ob.hide = False
            ob.select = True
            
            
        # before
        A = set(scene.objects[:])
        
        bpy.ops.object.duplicate()
        
        # after operation
        B = set(scene.objects[:])

        # whats the difference
        new_objects = (A ^ B)
        
        # make light material single user and update selection drivers
        bpy.ops.group.objects_remove_all()
        bpy.ops.group.create(name='BLS_Light')
        
        for lg in new_objects:
            if lg.name.startswith('BLS_LIGHT_GRP.'):
                controller = [c for c in family(lg) if c.name.startswith("BLS_CONTROLLER.")][0]
                lmesh = [l for l in family(lg) if l.name.startswith("BLS_LIGHT_MESH.")][0]
                
                light_mat = None
                for id, mat in enumerate(controller.data.materials):
                    if mat.name.startswith('BLS_icon_ctrl'):
                        mat = mat.copy()
                        controller.data.materials[id] = mat
                        
                        for d in mat.animation_data.drivers:
                            d.driver.variables[0].targets[0].id = scene.objects['BLS_LIGHT_MESH.'+controller.name.split('.')[1]]
                        
                        for d in mat.node_tree.animation_data.drivers:
                            for v in d.driver.variables:
                                v.targets[0].id = scene.objects['BLS_LIGHT_MESH.'+controller.name.split('.')[1]]
                                
                    elif mat.name.startswith('BLS_light'):
                        #mat = mat.copy()
                        light_mat = mat.copy()
                        controller.data.materials[id] = light_mat
                        light_mat.node_tree.nodes['Light Texture'].image = light_mat.node_tree.nodes['Light Texture'].image.copy()
                        
                for id, mat in enumerate(lmesh.data.materials):
                    if mat.name.startswith('BLS_light'):
                        lmesh.data.materials[id] = light_mat               
                            
        # revert visibility
        for ob in chain(obsToCopy, new_objects):
            ob.hide = True
            ob.hide_select = True
            
            if ob.name.startswith('BLS_LIGHT_MESH.') or \
               ob.name.startswith('BLS_CONTROLLER.'):
                ob.hide = False
                ob.hide_select = False
                
        profileName = props.profile_list[props.list_index].name
        
        bpy.ops.bls_list.new_profile()
        lastItemId = len(props.profile_list)-1
        
        # parent objects to new profile
        for ob in new_objects:
            scene.objects.unlink(ob)
            if ob.name.startswith('BLS_LIGHT_GRP.'):
                ob.parent = bpy.data.objects[props.profile_list[lastItemId].empty_name]
            
        props.profile_list[len(props.profile_list)-1].name = profileName + ' Copy'
        
        
        # place copied profile next to source profile
        while lastItemId > props.list_index+1:
            list.move(lastItemId-1, lastItemId)
            lastItemId -= 1
        
        context.area.spaces[0].layers = oldlaysArea
        context.scene.layers = oldlaysScene
        
        return{'FINISHED'}
    
    
 
class LIST_OT_MoveItem(bpy.types.Operator):
    """ Move an item in the list """

    bl_idname = "bls_list.move_profile"
    bl_label = "Move an profile in the list"
    bl_options = {"INTERNAL"}

    direction = bpy.props.EnumProperty(
                items=(
                    ('UP', 'Up', ""),
                    ('DOWN', 'Down', ""),))

    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list. """
        return len(context.scene.BLStudio.profile_list)


    def move_index(self, context):
        """ Move index of an item render queue while clamping it. """
        props = context.scene.BLStudio
        index = props.list_index
        list_length = len(props.profile_list) - 1 # (index starts at 0)
        new_index = 0

        if self.direction == 'UP':
            new_index = index - 1
        elif self.direction == 'DOWN':
            new_index = index + 1

        new_index = max(0, min(new_index, list_length))
        props.list_index = new_index


    def execute(self, context):
        props = context.scene.BLStudio
        list = props.profile_list
        index = props.list_index

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


def update_list_index(self, context):
    props = context.scene.BLStudio
    
    if len(props.profile_list) == 0: return
        
    selected_profile = props.profile_list[self.list_index]
    
    if selected_profile.empty_name == props.last_empty: return

    print('Index update {}'.format(self.list_index))
        
    #unlink current profile
    if context.scene.objects.find(props.last_empty) > -1: # in case of update after deletion
        for ob in family(context.scene.objects[props.last_empty]):
            ob['last_layers'] = ob.layers[:]
            context.scene.objects.unlink(ob)
        
    #link selected profile
    for ob in family(bpy.data.objects[selected_profile.empty_name]):
        print(ob.name)
        context.scene.objects.link(ob)
        ob.layers = [bool(l) for l in ob['last_layers']]
        
    props.last_empty = selected_profile.empty_name
    
        
        
# import/export
import json, time
script_file = os.path.realpath(__file__)
dir = os.path.dirname(script_file)

def parse_profile(context, props, profiles, internal_copy=False):
    plist = props.profile_list
    for profile in profiles:
        print(profile)
        bpy.ops.bls_list.new_profile()
        props.list_index = len(plist)-1
        plist[-1].name = profile["name"]
        if not internal_copy:
            date = time.localtime()
            plist[-1].name += ' {}-{:02}-{:02} {:02}:{:02}'.format(str(date.tm_year)[-2:], date.tm_mon, date.tm_mday, date.tm_hour, date.tm_min)

        #lgroups = [lg for lg in family(bpy.data.objects[props.profile_list[list_index].empty_name]) if "BLS_LIGHT_GRP" in lg.name]
        profile_empty = context.scene.objects[plist[-1].empty_name]
        
        handle = getLightHandle(profile_empty)    
        handle.location.x = profile['handle_position'][0]
        handle.location.y = profile['handle_position'][1]
        handle.location.z = profile['handle_position'][2]

        for light in profile["lights"]:
            # before
            A = set(profile_empty.children)
            
            bpy.ops.scene.add_blender_studio_light()
            
            # after operation
            B = set(profile_empty.children)
            
            # whats the difference
            lgrp = (A ^ B).pop()
            controller = [c for c in family(lgrp) if "BLS_CONTROLLER" in c.name][0]
            props.light_radius = light['radius']
            
            controller.location.x = light['position'][0]
            controller.location.y = light['position'][1]
            controller.location.z = light['position'][2]
            
            controller.scale.x = light['scale'][0]
            controller.scale.y = light['scale'][1]
            controller.scale.z = light['scale'][2]
            
            controller.rotation_euler.z = light['rotation']
            
            props.light_muted = light['mute']
            controller.material_slots[1].material.node_tree.nodes["Group"].inputs[2].default_value = light['Intensity']
            controller.material_slots[1].material.node_tree.nodes["Group"].inputs[3].default_value = light['Opacity']
            controller.material_slots[1].material.node_tree.nodes["Group"].inputs[4].default_value = light['Falloff']
            controller.material_slots[1].material.node_tree.nodes["Group"].inputs[5].default_value = light['Color Saturation']
            controller.material_slots[1].material.node_tree.nodes["Group"].inputs[6].default_value = light['Half']
            
            if os.path.isabs(light['tex']):
                controller.material_slots[1].material.node_tree.nodes["Light Texture"].image.filepath = light['tex']
            else:
                controller.material_slots[1].material.node_tree.nodes["Light Texture"].image.filepath = os.path.join(dir, "textures_real_lights", light['tex'])
                
class ImportProfiles(bpy.types.Operator):
    """ Import Profiles from File """
 
    bl_idname = "bls_list.import_profiles"
    bl_label = "Import Profiles"
    #bl_options = {"INTERNAL"}
    
    filepath = bpy.props.StringProperty(default="*.bls", subtype="FILE_PATH")
 
    @classmethod
    def poll(self, context):
        return True
 
    def execute(self, context):
        props = context.scene.BLStudio
        plist = props.profile_list
        
        with open(self.filepath, 'r') as f:
            file = f.read()
        f.closed
        
        file = json.loads(file)
        parse_profile(context, props, file["profiles"])
 
        return{'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

def compose_profile(list_index):
    props = bpy.context.scene.BLStudio
    
    profile_dict = {}
    profile_dict['name'] = props.profile_list[list_index].name
    profile_dict['lights']= []
    profile = bpy.data.objects[props.profile_list[list_index].empty_name]
    lgroups = [lg for lg in family(profile) if "BLS_LIGHT_GRP" in lg.name]
    handle = getLightHandle(profile)
    print(profile, handle)
    profile_dict['handle_position'] = [handle.location.x, handle.location.y, handle.location.z]
    for lg in lgroups:
        controller = [c for c in family(lg) if "BLS_CONTROLLER" in c.name][0]
        lmesh = [l for l in family(lg) if "BLS_LIGHT_MESH" in l.name][0]
        light = {}
        light['radius'] = lmesh.location.x
        light['position'] = [controller.location.x, controller.location.y, controller.location.z]
        light['scale'] = [controller.scale.x, controller.scale.y, controller.scale.z]
        light['rotation'] = controller.rotation_euler.z
        light['mute'] = props.light_muted
        texpath = controller.material_slots[1].material.node_tree.nodes["Light Texture"].image.filepath
        light['tex'] = texpath.split(bpy.path.native_pathsep("\\textures_real_lights\\"))[-1]
        
        light['Intensity'] = controller.material_slots[1].material.node_tree.nodes["Group"].inputs[2].default_value
        light['Opacity'] = controller.material_slots[1].material.node_tree.nodes["Group"].inputs[3].default_value
        light['Falloff'] = controller.material_slots[1].material.node_tree.nodes["Group"].inputs[4].default_value
        light['Color Saturation'] = controller.material_slots[1].material.node_tree.nodes["Group"].inputs[5].default_value
        light['Half'] = controller.material_slots[1].material.node_tree.nodes["Group"].inputs[6].default_value
        
        profile_dict['lights'].append(light)
        
    return profile_dict
        
class ExportProfiles(bpy.types.Operator):
    """ Export Profiles to File """
 
    bl_idname = "bls_list.export_profiles"
    bl_label = "Export"
    #bl_options = {"INTERNAL"}
    
    filepath = bpy.props.StringProperty(default="profile.bls", subtype="FILE_PATH")
    all = bpy.props.BoolProperty(default=False, name="Export All Profiles")
 
    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list """
        return len(context.scene.BLStudio.profile_list)
 
    def execute(self, context):
        props = context.scene.BLStudio
        index = props.list_index
            
        export_file = {}
        date = time.localtime()
        export_file['date'] = '{}-{:02}-{:02} {:02}:{:02}'.format(date.tm_year, date.tm_mon, date.tm_mday, date.tm_hour, date.tm_min)
        export_file['version'] = '1.01'
        profiles_to_export = export_file['profiles'] = []
        
        if self.all:
            for p in range(len(props.profile_list)):
                profiles_to_export.append(compose_profile(p))
        else:
            profiles_to_export.append(compose_profile(index))
        
        #file = open(self.filepath, 'w')
        #file.write(json.dumps(export_file, indent=4))
        #file.close()
        
        with open(self.filepath, 'w') as f:
            f.write(json.dumps(export_file, indent=4))
        f.closed
        
        return{'FINISHED'}
    
    def invoke(self, context, event):
        self.filepath = "profile.bls"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
class FindMissingTextures(bpy.types.Operator):
    """ Find Missing Textures """
 
    bl_idname = "bls.find_missing_textures"
    bl_label = "Find Missing Textures"
    #bl_options = {"INTERNAL"}
    
    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list """
        return len(context.scene.BLStudio.profile_list)
 
    def execute(self, context):
        bpy.ops.file.find_missing_files(directory=os.path.join(dir, "textures_real_lights"))        
        bpy.context.scene.frame_current = bpy.context.scene.frame_current
        return{'FINISHED'}

class CopyProfileToScene(bpy.types.Operator):
    """ Copy Light Profile to Scene """
 
    bl_idname = "bls_list.copy_profile_to_scene"
    bl_label = "Copy Profile to Scene"
    bl_property = "sceneprop"
    
    def get_scenes(self, context):
        return ((s.name, s.name, "Scene name") for i,s in enumerate(bpy.data.scenes))#global_vars["scenes"]
    
    sceneprop = EnumProperty(items = get_scenes)
    
    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list """
        return len(context.scene.BLStudio.profile_list)
 
    def execute(self, context):
        props = context.scene.BLStudio
        index = props.list_index
        
        profiles = [compose_profile(index),]
        
        context.screen.scene = bpy.data.scenes[self.sceneprop]
        context.scene.render.engine = 'CYCLES'
        if not context.scene.BLStudio.initialized:
            bpy.ops.scene.create_blender_light_studio()
        
        parse_profile(context, context.scene.BLStudio, profiles, internal_copy=True)
        
        return{'FINISHED'}
        
    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}
    

class CopyProfileMenu(bpy.types.Operator):
    """ Copy Light Profile """
 
    bl_idname = "bls_list.copy_profile_menu"
    bl_label = "Copy Profile"

    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list """
        return len(context.scene.BLStudio.profile_list)
    
    def execute(self, context):
        wm = context.window_manager
        def draw(self, context):
            layout = self.layout
            layout.operator_context='INVOKE_AREA'
            col = layout.column(align=True)
            col.operator('bls_list.copy_profile')
            col.operator('bls_list.copy_profile_to_scene')

        wm.popup_menu(draw, title="Copy Profile")
        return {'FINISHED'}