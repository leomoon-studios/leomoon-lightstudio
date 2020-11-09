import bpy
from bpy.props import BoolProperty, PointerProperty, FloatProperty, CollectionProperty, IntProperty, StringProperty, EnumProperty, FloatVectorProperty
from mathutils import Vector
from . light_profiles import ListItem, update_list_index
from . common import *
import os
from . import operators
from . import light_list
from . operators import VERBOSE
from . light_data import *

_ = os.sep

from . import bl_info

class LeoMoon_Light_Studio_Properties(bpy.types.PropertyGroup):
    initialized: BoolProperty(default = False)

    ''' Profile List '''
    profile_list: CollectionProperty(type = ListItem)
    list_index: IntProperty(name = "Index for profile_list", default = 0, update=update_list_index)
    last_empty: StringProperty(name="Name of last Empty holding profile", default="")

    light_list: CollectionProperty(type = light_list.LightListItem)
    light_list_index: IntProperty(name = "Index for light_list", default = 0, get=light_list.get_list_index, set=light_list.set_list_index)

    # def active_light_type_get(self):
    #     light_handle = bpy.context.object.parent
    #     visible_lights = [c for c in light_handle.children if c.visible_get()]
    #     if len(visible_lights) != 1:
    #         # TODO: fix it
    #         return 0
    #     light_object = visible_lights[0]
    #     if light_object.type == 'MESH':
    #         return 0
    #     else:
    #         return 1
    
    # def active_light_type_set(self, value):
    #     light_handle = bpy.context.object.parent
    #     basic_col = [l.users_collection[0] for l in light_handle.children if l.type == 'LIGHT'][0]
    #     advanced_col = [l.users_collection[0] for l in light_handle.children if l.type == 'MESH'][0]

    #     basic_view = find_view_layer(basic_col, bpy.context.view_layer.layer_collection)
    #     advanced_view = find_view_layer(advanced_col, bpy.context.view_layer.layer_collection)

    #     if value == 0:
    #         # ADVANCED
    #         basic_view.exclude = True
    #         advanced_view.exclude = False
    #         bpy.context.view_layer.objects.active = advanced_col.objects[0]
    #     elif value == 1:
    #         # BASIC
    #         basic_view.exclude = False
    #         advanced_view.exclude = True
    #         bpy.context.view_layer.objects.active = basic_col.objects[0]


    # active_light_type: EnumProperty(
    #     name="Light Type",
    #     items=(
    #         ('ADVANCED', "Advanced", "Cycles only"),
    #         ('BASIC', "Basic", "Cycles & EEVEE"),
    #     ),
    #     default='ADVANCED',
    #     get=active_light_type_get,
    #     set=active_light_type_set,
    # )

class LeoMoon_Light_Studio_Object_Properties(bpy.types.PropertyGroup):
    light_name: StringProperty()
    order_index: IntProperty()
    
    def active_light_type_update(self, context):
        # if not context.object:
        #     light_handle = bpy.data.objects[context.scene.LLStudio.light_list[self.order_index].handle_name]
        #     print(light_handle)
        # else:
        #     light_handle = context.object.parent
        try:
            light_handle = bpy.data.objects[context.scene.LLStudio.light_list[self.order_index].handle_name]
        except:
            return
        
        try:
            basic_col = [l.users_collection[0] for l in light_handle.children if l.type == 'LIGHT'][0]
            advanced_col = [l.users_collection[0] for l in light_handle.children if l.type == 'MESH'][0]

            basic_view = find_view_layer(basic_col, context.view_layer.layer_collection)
            advanced_view = find_view_layer(advanced_col, context.view_layer.layer_collection)
            if self.type == 'ADVANCED':
                # ADVANCED
                basic_view.exclude = True
                advanced_view.exclude = False
                bpy.context.view_layer.objects.active = advanced_col.objects[0]
                advanced_col.objects[0].select_set(True)
            elif self.type == 'BASIC':
                # BASIC
                basic_view.exclude = False
                advanced_view.exclude = True
                bpy.context.view_layer.objects.active = basic_col.objects[0]
                basic_col.objects[0].select_set(True)
                basic_col.objects[0].data.LLStudio.intensity = basic_col.objects[0].data.LLStudio.intensity
        except IndexError:
            lls_col = light_handle.users_collection[0]
            light = salvage_data(lls_col)
            light_root = light_handle.parent.parent
            profile_collection = light_root.parent.users_collection[0]
            family_obs = family(light_root)
            bpy.ops.object.delete({"selected_objects": list(family_obs)}, use_global=True)
            bpy.data.collections.remove(lls_col)
            light_from_dict(light, profile_collection)
    
    type: EnumProperty(
        name="Light Type",
        items=(
            ('ADVANCED', "Advanced", "Cycles only"),
            ('BASIC', "Basic", "Cycles & EEVEE"),
        ),
        default='ADVANCED',
        update=active_light_type_update,
    ) 

from . operators import AREA_DEFAULT_SIZE
class LeoMoon_Light_Studio_Light_Properties(bpy.types.PropertyGroup):
    def color_update(self, context):
        bpy.context.object.data.color = Vector((1,1,1)).lerp(Vector(self.color), self.color_saturation)

    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        default=(1,1,1),
        size=3,
        soft_min=0,
        soft_max=1,
        update=color_update,
    )
    color_saturation: FloatProperty(
        name="Color Saturation",
        min=0,
        max=1,
        update=color_update,
    )
    def light_power_formula(self, context):
        if not bpy.context.object.type == 'LIGHT':
            return
        
        try:
            bpy.context.object.data.energy = self.intensity * context.object.parent.scale.x * context.object.parent.scale.z * 250
        except:
            bpy.context.object.data.energy = self.intensity

    intensity: FloatProperty(
        name="Intensity",
        soft_min=0,
        soft_max=10000,
        default=2,
        update=light_power_formula,
    )

class CreateBlenderLightStudio(bpy.types.Operator):
    bl_idname = "scene.create_leomoon_light_studio"
    bl_label = "Create LightStudio"
    bl_description = "Append LeoMoon LightStudio to current scene"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and not context.scene.LLStudio.initialized

    def execute(self, context):
        script_file = os.path.realpath(__file__)
        dir = os.path.dirname(script_file)

        bpy.ops.wm.append(filepath=_+'LLS4.blend'+_+'Collection'+_,
        directory=os.path.join(dir,"LLS4.blend"+_+"Collection"+_),
        filename="LLS",
        active_collection=False)

        bpy.ops.lls_list.new_profile()

        context.scene.LLStudio.initialized = True

        bpy.context.scene.render.engine = 'CYCLES'

        # add the first light
        # bpy.ops.object.select_all(action='DESELECT')
        # bpy.ops.scene.add_leomoon_studio_light()

        return {"FINISHED"}

class DeleteBlenderLightStudio(bpy.types.Operator):
    bl_idname = "scene.delete_leomoon_light_studio"
    bl_label = "Delete LightStudio"
    bl_description = "Delete LeoMoon LightStudio from current scene"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and context.scene.LLStudio.initialized

    def execute(self, context):
        scene = context.scene
        scene.LLStudio.initialized = False

        # close control panel
        from . operators.modal import close_control_panel
        close_control_panel()

        ''' for each profile from this scene: delete objects then remove from list '''
        while len(context.scene.LLStudio.profile_list):
            bpy.ops.lls_list.delete_profile()

        obsToRemove = [ob for ob in scene.objects if isFamily(ob)]
        for ob in obsToRemove:
            for c in ob.users_collection:
                c.objects.unlink(ob)
            ob.user_clear()
            ob.use_fake_user = False
            bpy.data.objects.remove(ob)

        context.scene.collection.children.unlink(get_lls_collection(context))

        return {"FINISHED"}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Deleting LightStudio is irreversible!")
        col.label(text="Your lighting setup will be lost.")

class SetBackground(bpy.types.Operator):
    bl_idname = "scene.set_light_studio_background"
    bl_description = "Darken background and disable background influence"
    bl_label = "Background Setup (Optional)"
    bl_options = {"REGISTER", "UNDO"}
    # @classmethod
    # def poll(self, context):
        # """ Enable if there's something in the list """
        # return len(context.scene.LLStudio.profile_list)

    def execute(self, context):
        bpy.context.scene.render.engine = 'CYCLES'
        if bpy.data.worlds.get('LightStudio') is None:
            bpy.context.scene.world = bpy.data.worlds.new('LightStudio')
        else:
            bpy.context.scene.world = bpy.data.worlds['LightStudio']
        # bpy.context.scene.world = bpy.data.worlds.new("LightStudio")
        bpy.context.scene.world.use_nodes = True
        bpy.context.scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.00802319, 0.00802319, 0.00802319, 1)
        bpy.context.scene.world.cycles_visibility.diffuse = False
        bpy.context.scene.world.cycles_visibility.glossy = False
        bpy.context.scene.world.cycles_visibility.transmission = False
        return {"FINISHED"}

class AddBSLight(bpy.types.Operator):
    bl_idname = "scene.add_leomoon_studio_light"
    bl_label = "Add Studio Light"
    bl_description = "Add a new light to studio"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.LLStudio.initialized
        # return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and context.scene.LLStudio.initialized

    def execute(self, context):
        script_file = os.path.realpath(__file__)
        dir = os.path.dirname(script_file)

        scene = context.scene
        lls_collection, profile_collection, profile, handle = llscol_profilecol_profile_handle(context)

        filepath = os.path.join(dir,"LLS4.blend")
        # load a single scene we know the name of.
        with bpy.data.libraries.load(filepath) as (data_from, data_to):
            data_to.collections = ["LLS_Light"]

        for collection in data_to.collections:
            if collection is not None:
                profile_collection.children.link(collection)

                advanced_light_collection = [c for c in collection.children if c.name.startswith('LLS_Advanced')][0]
                basic_light_collection = [c for c in collection.children if c.name.startswith('LLS_Basic')][0]
                
                new_objects = collection.objects[:]
                # new_objects += [ob for col in collection.children for ob in col.objects]
                new_objects += advanced_light_collection.objects[:]
                new_objects += basic_light_collection.objects[:]
                for ob in new_objects:
                    ob.use_fake_user = True

                llslight = [l for l in new_objects if l.name.startswith('LLS_LIGHT.')][0]
                llslight.parent = profile

                bpy.ops.object.select_all(action='DESELECT')
                # light = [p for p in new_objects if p.name.startswith('LLS_LIGHT_MESH')][0]
                # light.select_set(True)
                # context.view_layer.objects.active = light

                light_handle = [p for p in new_objects if p.name.startswith('LLS_LIGHT_HANDLE')][0]
                light_handle.LLStudio.order_index = len(context.scene.LLStudio.light_list)

                basic_light_layer = find_view_layer(basic_light_collection, context.view_layer.layer_collection)
                advanced_light_layer = find_view_layer(advanced_light_collection, context.view_layer.layer_collection)
                if context.scene.render.engine == "BLENDER_EEVEE":
                    # basic_light_layer.exclude = False
                    # advanced_light_layer.exclude = True
                    light_object = basic_light_collection.objects[0]
                    light_handle.LLStudio.type = 'BASIC'
                else:
                    # basic_light_layer.exclude = True
                    # advanced_light_layer.exclude = False
                    light_object = advanced_light_collection.objects[0]
                    light_handle.LLStudio.type = 'ADVANCED'
                
                context.view_layer.objects.active = light_object
                light_object.select_set(True)
                print(light_object)

                # light = advanced_light_layer.collection.objects[0]
                # light.LLStudio.order_index = len(context.scene.LLStudio.light_list)
                # light_handle.LLStudio.order_index = len(context.scene.LLStudio.light_list)




        #####

        c = light_handle.constraints.new('COPY_LOCATION')
        c.target = handle
        c.use_x = True
        c.use_y = True
        c.use_z = True
        c.use_offset = True
        # scene.frame_current = bpy.context.scene.frame_current # refresh hack
        # refreshMaterials()

        operators.update()
        light_list.update_light_list_set(context)

        return {"FINISHED"}

class DeleteBSLight(bpy.types.Operator):
    bl_idname = "scene.delete_leomoon_studio_light"
    bl_label = "Delete Studio Light"
    bl_description = "Delete selected light from studio"
    bl_options = {"REGISTER", "UNDO"}

    confirm: BoolProperty(default=True)
    @classmethod
    def poll(cls, context):
        light = context.active_object
        if not context.area:
            return True
        return context.area.type == 'VIEW_3D' and \
               context.mode == 'OBJECT' and \
               context.scene.LLStudio.initialized and \
               light and \
               light.name.startswith('LLS_LIGHT')

    def execute(self, context):
        scene = context.scene
        light = context.object

        lls_light = findLightGrp(light)
        lls_light_collection = lls_light.users_collection[0]
        col_to_remove = [lls_light_collection,]+ lls_light_collection.children[:]
        if lls_light_collection.name.startswith('LLS_Light'):
            bpy.ops.object.delete({"selected_objects": family(lls_light)}, use_global=True)
            for col in col_to_remove:
                bpy.data.collections.remove(col)

        operators.update()
        light_list.update_light_list_set(context)

        return {"FINISHED"}

    def invoke(self, context, event):
        wm = context.window_manager
        if self.confirm:
            return wm.invoke_props_dialog(self)
        else:
            return self.execute(context)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="OK?")

class BUILTIN_KSI_LightStudio(bpy.types.KeyingSetInfo):
    bl_label = "LightStudio KeyingSet"

    # poll - test for whether Keying Set can be used at all
    def poll(ksi, context):
        return context.active_object or context.selected_objects and context.scene.LLStudio.initialized

    # iterator - go over all relevant data, calling generate()
    def iterator(ksi, context, ks):
        for ob in (l for l in context.selected_objects if l.name.startswith("LLS_LIGHT")):
            ksi.generate(context, ks, ob)

    # generator - populate Keying Set with property paths to use
    def generate(ksi, context, ks, data):
        id_block = data.id_data

        lls_collection = get_collection(id_block)
        light_mesh = [m for m in lls_collection.objects if m.name.startswith("LLS_LIGHT_MESH")][0]
        lls_actuator = light_mesh.parent

        ks.paths.add(light_mesh, "location", index=0, group_method='KEYINGSET')
        ks.paths.add(light_mesh, "rotation_euler", index=0, group_method='KEYINGSET')
        ks.paths.add(light_mesh, "scale", group_method='KEYINGSET')
        ks.paths.add(lls_actuator, "rotation_euler", group_method='KEYINGSET')