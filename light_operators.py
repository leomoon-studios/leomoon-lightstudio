import bpy
from bpy.props import BoolProperty, FloatProperty, CollectionProperty, IntProperty, StringProperty, EnumProperty, FloatVectorProperty
from mathutils import Vector
from . light_profiles import ListItem, update_profile_list_index, _update_profile_list_index
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
    profile_list_index: IntProperty(name = "Index for profile_list", default = 0, update=update_profile_list_index)
    last_empty: StringProperty(name="Name of last Empty holding profile", default="")

    def multimode_refresh(props, context):
        if props.profile_multimode:
            if len(props.profile_list) == 0:
                return
            props.profile_list_index = min(len(props.profile_list), props.profile_list_index)
            tmp_idx = props.profile_list_index
            selected_profile = props.profile_list[props.profile_list_index]
            for profile in props.profile_list:
                profile_collection = get_collection(bpy.data.objects[profile.empty_name])

                lls_collection = get_lls_collection(context)

                if profile_collection.name == selected_profile.empty_name:
                    selected_profile.enabled = True

                if profile.enabled:
                    #link selected profile
                    profile_col = bpy.data.collections[profile.empty_name]
                    if profile_col.name not in lls_collection.children:
                        lls_collection.children.link(profile_col)
                else:
                    #unlink profile
                    if profile_collection:
                        if profile_collection.name in lls_collection.children:
                            lls_collection.children.unlink(profile_collection)

            for idx, profile in enumerate(props.profile_list):
                if props.profile_list_index == idx: continue
                props.profile_list_index = idx
            props.profile_list_index = tmp_idx
        else:
            _update_profile_list_index(props, context, multimode_override=True)


    profile_multimode: BoolProperty(default=False, name="Multi Profile Mode", description="Use many profiles at once.", update=multimode_refresh)

    light_list: CollectionProperty(type = light_list.LightListItem)
    light_list_index: IntProperty(name = "Index for light_list", default = 0, get=light_list.get_list_index, set=light_list.set_list_index)

    def mode_change_func(self, context):
        if self.lls_mode == "NORMAL":
            roots = [o for o in context.scene.objects if o.name.startswith("LEOMOON_LIGHT_STUDIO")]
            for root in roots:
                all_elems = family(root)
                for elem in all_elems:
                    matches = ['LLS_LIGHT_HANDLE']
                    if any(x in elem.name for x in matches):
                        elem.hide_viewport = True
                        elem.hide_select = True
        elif self.lls_mode == "ANIMATION":
            # force selection msgbus callback
            bpy.context.view_layer.objects.active = bpy.context.view_layer.objects.active


    lls_mode: EnumProperty(items=[("NORMAL", "Normal", "Normal"), ("ANIMATION", "Animation", "Animation")],
            name="Mode",
            description="Use Animated mode to select all light components for easier keyframe editing.",
            update=mode_change_func,
            default="NORMAL")


class LeoMoon_Light_Studio_Object_Properties(bpy.types.PropertyGroup):
    light_name: StringProperty()
    order_index: IntProperty()

    def active_light_type_update(self, context):
        try:
            light_handle = bpy.data.objects[context.scene.LLStudio.light_list[self.order_index].handle_name]
        except Exception as e:
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
        except IndexError as e:
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
        if not bpy.context.object or not bpy.context.object.type == 'LIGHT':
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

        # In pre 3.0 Blenders, this apending (with active_collection=False) added LLS collection in the scene master collection.
        # Unfortunatelly, in 3.0 LLS collection is wrapped in 'Collection 2'
        # so, we have to make sure master collection is the active collection and append it with active_collection=True
        context.view_layer.active_layer_collection = context.view_layer.layer_collection
        bpy.ops.wm.append(filepath=_+'LLS4.blend'+_+'Collection'+_,
        directory=os.path.join(dir,"LLS4.blend"+_+"Collection"+_),
        filename="LLS",
        active_collection=True)

        bpy.ops.lls_list.new_profile()

        context.scene.LLStudio.initialized = True

        # bpy.context.scene.render.engine = 'CYCLES'

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
        #bring back the default wold settings
        if bpy.data.worlds.get('World') is None:
            bpy.context.scene.world = bpy.data.worlds.new('World')
            bpy.context.scene.world.use_nodes = True
            bpy.context.scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.050876, 0.050876, 0.050876, 1)
            bpy.context.scene.world.cycles_visibility.diffuse = True
            bpy.context.scene.world.cycles_visibility.glossy = True
            bpy.context.scene.world.cycles_visibility.transmission = True
        else:
            bpy.context.scene.world = bpy.data.worlds['World']
            bpy.context.scene.world.use_nodes = True
            bpy.context.scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.050876, 0.050876, 0.050876, 1)
            bpy.context.scene.world.cycles_visibility.diffuse = True
            bpy.context.scene.world.cycles_visibility.glossy = True
            bpy.context.scene.world.cycles_visibility.transmission = True

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
        # bpy.context.scene.render.engine = 'CYCLES'
        if bpy.data.worlds.get('LightStudio') is None:
            bpy.context.scene.world = bpy.data.worlds.new('LightStudio')
            bpy.context.scene.world.use_nodes = True
            bpy.context.scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.008, 0.008, 0.008, 1)
            bpy.context.scene.world.cycles_visibility.diffuse = False
            bpy.context.scene.world.cycles_visibility.glossy = False
            bpy.context.scene.world.cycles_visibility.transmission = False
        else:
            bpy.context.scene.world = bpy.data.worlds['LightStudio']
            bpy.context.scene.world.use_nodes = True
            bpy.context.scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.008, 0.008, 0.008, 1)
            bpy.context.scene.world.cycles_visibility.diffuse = False
            bpy.context.scene.world.cycles_visibility.glossy = False
            bpy.context.scene.world.cycles_visibility.transmission = False

        return {"FINISHED"}

class SwitchToCycles(bpy.types.Operator):
    bl_idname = "scene.switch_to_cycles"
    bl_description = "Change render engine to cycles"
    bl_label = "Switch to Cycles"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.context.scene.render.engine = 'CYCLES'
        return {"FINISHED"}

class AddLLSLight(bpy.types.Operator):
    bl_idname = "scene.add_leomoon_studio_light"
    bl_label = "Add Studio Light"
    bl_description = "Add a new light to studio"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        props = context.scene.LLStudio
        return props.initialized and (props.profile_list_index < len(props.profile_list) and props.profile_list[props.profile_list_index].enabled or not props.profile_multimode)

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

                # basic_light_layer = find_view_layer(basic_light_collection, context.view_layer.layer_collection)
                # advanced_light_layer = find_view_layer(advanced_light_collection, context.view_layer.layer_collection)
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
        props = context.scene.LLStudio
        return context.area.type == 'VIEW_3D' and \
               context.mode == 'OBJECT' and \
               props.initialized and \
               light and \
               light.name.startswith('LLS_LIGHT') and \
               (props.profile_list_index < len (props.profile_list) and props.profile_list[props.profile_list_index].enabled or not props.profile_multimode)

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

        lls_root = findLightGrp(id_block)
        family_obs = family(lls_root)

        lls_handle = [m for m in family_obs if m.name.startswith("LLS_LIGHT_HANDLE")][0]
        lls_actuator = lls_handle.parent

        ks.paths.add(lls_handle, "location", index=2, group_method='KEYINGSET')
        ks.paths.add(lls_handle, "rotation_euler", index=1, group_method='KEYINGSET')
        ks.paths.add(lls_handle, "scale", group_method='KEYINGSET')
        ks.paths.add(lls_actuator, "rotation_euler", group_method='KEYINGSET')

from bpy.app.handlers import persistent
@persistent
def lightstudio_update_frame(scene, depsgraph=None):
    if not scene.LLStudio.initialized:
        return

    # light energy sync
    for lls_area in [obj for obj in scene.objects if obj.name.startswith("LLS_LIGHT_AREA.")]:
        color = lls_area.data.LLStudio.color
        color_saturation = lls_area.data.LLStudio.color_saturation
        intensity = lls_area.data.LLStudio.intensity
        lls_area.data.color = Vector((1,1,1)).lerp(color, color_saturation)

        try:
            lls_area.data.energy = intensity * lls_area.parent.scale.x * lls_area.parent.scale.z * 250
        except:
            lls_area.data.energy = intensity

subscribe_to = bpy.types.LayerObjects, "active"

def msgbus_callback(*args):
    active_object = bpy.context.active_object

    if not active_object or not bpy.context.scene.LLStudio.initialized or bpy.context.scene.LLStudio.lls_mode=="NORMAL":
        return

    if active_object.name.startswith("LLS_LIGHT_MESH") or active_object.name.startswith("LLS_LIGHT_AREA"):
        root = findLightGrp(active_object)
        lls_rotation = root.children[0]
        lls_rotation.hide_viewport = False
        lls_rotation.hide_select = False
        lls_rotation.select_set(True)
        lls_light_handle = lls_rotation.children[0]
        lls_light_handle.hide_viewport = False
        lls_light_handle.hide_select = False
        lls_light_handle.select_set(True)

        try:
            light_group_list = [n for n in active_object.active_material.node_tree.nodes if n.name.startswith('Group')]
            if light_group_list:
                light_group_list[0].select=True
        except:
            print("No LLS Material node found in the material.")


owner = object()

@persistent
def lightstudio_load_post(load_handler):
    bpy.msgbus.subscribe_rna(
        key=subscribe_to,
        owner=owner,
        args=(),
        notify=msgbus_callback,
    )

def register():
    bpy.app.handlers.frame_change_post.append(lightstudio_update_frame)
    bpy.app.handlers.load_post.append(lightstudio_load_post)
    lightstudio_load_post(None)


def unregister():
    bpy.app.handlers.frame_change_post.remove(lightstudio_update_frame)
    bpy.msgbus.clear_by_owner(owner)
    bpy.app.handlers.load_post.remove(lightstudio_load_post)