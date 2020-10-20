import bpy
from bpy_extras import view3d_utils
from math import *
from mathutils.geometry import intersect_line_sphere
from mathutils import Vector
from bpy.props import *
from . common import isFamily, family, findLightGrp, getLightMesh, getLightController, get_user_keymap_item
from . operators import LightOperator


def raycast(context, event, diff):
    """Run this function on left mouse, execute the ray cast"""
    # get the context arguments
    region = context.region
    rv3d = context.region_data
    coord = event.mouse_region_x, event.mouse_region_y

    # get the ray from the viewport and mouse
    view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)

    ray_target = ray_origin + view_vector

    def visible_objects_and_duplis():
        """Loop over (object, matrix) pairs (mesh only)"""

        for obj in context.visible_objects:
            if isFamily(obj):
                continue

            if obj.type == 'MESH':
                yield (obj, obj.matrix_world.copy())

            if obj.instance_type != 'NONE':
                depsgraph = context.depsgraph
                for dup in depsgraph.object_instances:
                    obj_dupli = dup.object
                    if obj_dupli.type == 'MESH':
                        yield (obj_dupli, dup.matrix_world.copy())

    def obj_ray_cast(obj, matrix):
        """Wrapper for ray casting that moves the ray into object space"""

        # get the ray relative to the object
        matrix_inv = matrix.inverted()
        ray_origin_obj = matrix_inv @ ray_origin
        ray_target_obj = matrix_inv @ ray_target
        ray_direction_obj = ray_target_obj - ray_origin_obj

        # cast the ray
        success, location, normal, face_index = obj.ray_cast(ray_origin_obj, ray_direction_obj)

        if success:
            return location, normal, face_index
        else:
            return None, None, None

    # cast rays and find the closest object
    best_length_squared = -1.0
    best_obj = None
    normal = None
    location = None

    for obj, matrix in visible_objects_and_duplis():
        if obj.type == 'MESH':
            hit, hit_normal, face_index = obj_ray_cast(obj, matrix)
            if hit is not None:
                hit_world = matrix @ hit
                length_squared = (hit_world - ray_origin).length_squared
                if best_obj is None or length_squared < best_length_squared:
                    best_length_squared = length_squared
                    best_obj = obj
                    normal = hit_normal # local space
                    location = hit_world


    if best_obj is None:
        return {'RUNNING_MODAL'}

    # convert normal from local space to global
    matrix = best_obj.matrix_world
    matrix_new = matrix.to_3x3().inverted().transposed()
    normal = matrix_new @ normal
    normal.normalize()

    #####
    profile = findLightGrp(context.active_object).parent
    handle = [ob for ob in profile.children if ob.name.startswith('LLS_HANDLE')][0]
    lightmesh = getLightMesh()
    actuator = lightmesh.parent
    position = intersect_line_sphere(
        location - handle.location,
        (normal if diff else view_vector.reflect(normal)) + location - handle.location,
        Vector((0,0,0)),
        lightmesh.location.x,
        False,
        )[0]


    if not position:
        return {'RUNNING_MODAL'}

    # ctrl x
    x,y,z = position
    actuator.rotation_euler.x = atan2(x, -y)

    # ctrl y
    deg = copysign(degrees(Vector.angle(Vector((x,y,z)), Vector((x,y,0)))), z)
    actuator.rotation_euler.y = copysign(Vector.angle(Vector((x,y,z)), Vector((x,y,0))), z)

class LLSLightBrush(bpy.types.Operator, LightOperator):
    """Click on object to position light and reflection"""
    bl_idname = "lls.light_brush"
    bl_label = "Light Brush"
    bl_options = {"UNDO"}

    aux: BoolProperty(default=False) # is aux operator working
    normal_type: BoolProperty(default=False)

    def modal(self, context, event):
        # print(event.type, event.value)
        if self.aux:
            if event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'ESC', 'RET', 'NUMPAD_ENTER'}:
                self.aux = False
            return {'RUNNING_MODAL'}

        context.area.header_text_set(text=f"[LM] Select Face,  [ESC/RM] Quit,  [N] {'Reflection | [Normal]' if self.normal_type else '[Reflection] | Normal'}")

        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'Z', 'LEFT_SHIFT', 'LEFT_ALT', 'LEFT_CTRL'}:
            # allow navigation
            return {'PASS_THROUGH'}
        elif event.type in {'RIGHTMOUSE', 'ESC', 'RET', 'NUMPAD_ENTER'}:
            context.area.header_text_set(text=None)
            return {'FINISHED'}
        elif event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                raycast(context, event, self.normal_type)
                return {'RUNNING_MODAL'}
            elif event.value == 'RELEASE':
                return {'PASS_THROUGH'}
        elif event.type == 'MOUSEMOVE':
            if event.value == 'PRESS':
                raycast(context, event, self.normal_type)
                return {'PASS_THROUGH'}
        elif event.type == 'N' and event.value == 'PRESS':
            self.normal_type = not self.normal_type

        #return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.space_data.type == 'VIEW_3D':
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be a View3d")
            return {'CANCELLED'}

class OverrideContext:
    pass
class OverrideEvent:
    pass
key_released = False
class OT_LLSFast3DEdit(bpy.types.Operator, LightOperator):
    """Point on object to position light and reflection"""
    bl_idname = "light_studio.fast_3d_edit"
    bl_label = "Light Brush"
    bl_options = {"UNDO"}

    continuous: BoolProperty(default=False, name="Hold to use", description="Button behaviour.\n ON: Hold button to use. Release button to stop.\n OFF: Hold LMB to use, release LMB to stop.")
    normal_type: BoolProperty(default=False, name="Light along normal", description="Default reflection type.\n ON: Light along normal\n OFF: surface reflection (what you are looking for in most cases)")

    def modal(self, context, event):
        screens = [window.screen for window in context.window_manager.windows]
        regions3d = [(area.spaces[0].region_3d, region) for screen in screens for area in screen.areas if area.type == context.area.type for region in area.regions if region.type == context.region.type]
        active_region = context.region
        active_region_data = context.region_data
        for region_data, region in regions3d:
            if event.mouse_x >= region.x and event.mouse_x <= region.x + region.width and \
                event.mouse_y >= region.y and event.mouse_y <= region.y + region.height:
                active_region = region
                active_region_data = region_data
                break

        override_context = OverrideContext()
        override_context.region = active_region
        override_context.region_data = active_region_data
        override_context.visible_objects = context.visible_objects
        override_context.active_object = context.active_object
        if hasattr(context, 'depsgraph'):
            override_context.depsgraph = context.depsgraph
        override_event = OverrideEvent()
        override_event.mouse_region_x = event.mouse_x - active_region.x
        override_event.mouse_region_y = event.mouse_y - active_region.y


        global key_released
        context.area.header_text_set(text=f"[LM] Select Face,  [ESC/RM] Quit,  [N] {'Reflection | [Normal]' if self.normal_type else '[Reflection] | Normal'}")
        # print(event.type, event.value)
        if self.continuous:
            if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'LEFT_SHIFT', 'LEFT_ALT', 'LEFT_CTRL'}:
                # allow navigation
                return {'PASS_THROUGH'}
            elif event.type in {'RIGHTMOUSE', 'ESC', 'RET', 'NUMPAD_ENTER'}:
                context.area.header_text_set(text=None)
                return {'FINISHED'}
            elif event.type == 'N' and event.value == 'PRESS':
                self.normal_type = not self.normal_type
                return {'RUNNING_MODAL'}
            elif event.type == 'MOUSEMOVE':
                raycast(override_context, override_event, self.normal_type)
                return {'PASS_THROUGH'}
            elif event.value == 'RELEASE' and not event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE', 'N'}:
                context.area.header_text_set(text=None)
                return {'FINISHED'}
            elif event.value == 'RELEASE':
                key_released = True
                return {'PASS_THROUGH'}
        else:
            if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'LEFT_SHIFT', 'LEFT_ALT', 'LEFT_CTRL'}:
                # allow navigation
                return {'PASS_THROUGH'}
            elif event.type in {'RIGHTMOUSE', 'ESC', 'RET', 'NUMPAD_ENTER'}:
                context.area.header_text_set(text=None)
                return {'FINISHED'}
            elif event.type == 'N' and event.value == 'PRESS':
                self.normal_type = not self.normal_type
                return {'RUNNING_MODAL'}
            elif event.type in {'MOUSEMOVE', 'LEFTMOUSE'} and event.value == 'PRESS' and key_released:
                raycast(override_context, override_event, self.normal_type)
                return {'PASS_THROUGH'}
            elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and key_released:
                context.area.header_text_set(text=None)
                return {'FINISHED'}
            elif event.type in {self.keymap_key, 'LEFTMOUSE'} and event.value == 'RELEASE':
                key_released = True
                return {'PASS_THROUGH'}

        #return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        km, kmi = get_user_keymap_item('Object Mode', self.__class__.bl_idname)
        self.keymap_key = kmi.type if kmi else 'F'
        global key_released
        key_released = False
        if self.continuous:
            raycast(context, event, self.normal_type)
        return {'RUNNING_MODAL'}

addon_keymaps = []
def add_shortkeys():
    wm = bpy.context.window_manager
    addon_km = wm.keyconfigs.addon.keymaps.new(name='Object Mode', space_type="EMPTY")

    addon_kmi = addon_km.keymap_items.new(OT_LLSFast3DEdit.bl_idname, 'F', 'PRESS')
    addon_kmi.properties.continuous = False

    addon_keymaps.append((addon_km, addon_kmi))

def remove_shortkeys():
    wm = bpy.context.window_manager
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)

    addon_keymaps.clear()