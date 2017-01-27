import bpy
from bpy.props import StringProperty, PointerProperty, FloatProperty
import os
from . common import isFamily, family, findLightGrp
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
        
        #if len([prof for prof in profile.parent.children if prof.name.startswith('BLS_PROFILE.')]) > 1:
        if len([prof for prof in context.scene.objects if prof.name.startswith('BLS_PROFILE.') and isFamily(prof)]) > 1:
            #profile already exists
            context.scene.objects.unlink(profile)
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
    bl_label = "Copy an profile in the list"
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
        
        # make icon material single user and update selection drivers
        bpy.ops.group.objects_remove_all()
        bpy.ops.group.create(name='BLS_Light')
        for ob in new_objects:
            if ob.name.startswith('BLS_CONTROLLER.'):
                for id, mat in enumerate(ob.data.materials):
                    if mat.name.startswith('BLS_icon_ctrl'):
                        mat = mat.copy()
                        ob.data.materials[id] = mat
                        
                        for d in mat.animation_data.drivers:
                            d.driver.variables[0].targets[0].id = scene.objects['BLS_LIGHT_MESH.'+ob.name.split('.')[1]]
                        
                        for d in mat.node_tree.animation_data.drivers:
                            for v in d.driver.variables:
                                v.targets[0].id = scene.objects['BLS_LIGHT_MESH.'+ob.name.split('.')[1]]
                            
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
        context.scene.objects.link(ob)
        ob.layers = [bool(l) for l in ob['last_layers']]
        
    props.last_empty = selected_profile.empty_name
    
        