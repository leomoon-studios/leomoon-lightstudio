import bpy
from bpy_extras import view3d_utils
from math import *
from mathutils.geometry import intersect_line_sphere
from mathutils import Vector
from bpy.props import *
from . common import isFamily, family, findLightGrp, getLightMesh, getLightController


           
def raycast(context, event, diff):
    """Run this function on left mouse, execute the ray cast"""
    # get the context arguments
    scene = context.scene
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
    handle = [ob for ob in profile.children if ob.name.startswith('BLS_HANDLE')][0]
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

class BLSLightBrush(bpy.types.Operator):
    """Click on object to position light and reflection"""
    bl_idname = "bls.light_brush"
    bl_label = "Light Brush"
    bl_options = {"UNDO"}
    
    aux: BoolProperty(default=False) # is aux operator working
    diffuse_type: BoolProperty(default=False)
    
    @classmethod
    def poll(cls, context):
        light = context.active_object
        return context.area.type == 'VIEW_3D' and \
               context.mode == 'OBJECT' and \
               context.scene.BLStudio.initialized and \
               light and \
               isFamily(light) and \
               not (light.name.startswith('BLS_PANEL') or light.name.startswith('BLS_PROFILE') or light.name.startswith('BLS_LIGHT_GRP'))

    def modal(self, context, event):
        print(event.type, event.value)
        if self.aux:
            if event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'ESC', 'RET', 'NUMPAD_ENTER'}:
                self.aux = False
            return {'RUNNING_MODAL'}
        
        context.area.header_text_set(text=f"[LM] Select Face,  [ESC/RM] Quit,  [N] {'Reflection | [Normal]' if self.diffuse_type else '[Reflection] | Normal'}")
        
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'Z', 'LEFT_SHIFT', 'LEFT_ALT', 'LEFT_CTRL'}:
            # allow navigation
            return {'PASS_THROUGH'}
        elif event.type in {'RIGHTMOUSE', 'ESC', 'RET', 'NUMPAD_ENTER'}:
            context.area.header_text_set(text=None)
            return {'FINISHED'}
        elif event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                raycast(context, event, self.diffuse_type)
                return {'RUNNING_MODAL'}
            elif event.value == 'RELEASE':
                return {'PASS_THROUGH'}
        elif event.type == 'MOUSEMOVE':
            if event.value == 'PRESS':
                raycast(context, event, self.diffuse_type)
                return {'PASS_THROUGH'}
        elif event.type == 'N' and event.value == 'PRESS':
            self.diffuse_type = not self.diffuse_type

        #return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.space_data.type == 'VIEW_3D':
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be a View3d")
            return {'CANCELLED'}