import bpy
from bpy_extras import view3d_utils
from math import *
from mathutils.geometry import intersect_line_sphere
from mathutils import Vector
from bpy.props import *
from . common import isFamily, family, findLightGrp, getLightMesh, getLightController


           
def raycast(context, event, diff):
    controller = getLightController()
    #####
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

            if obj.dupli_type != 'NONE':
                obj.dupli_list_create(scene)
                for dob in obj.dupli_list:
                    obj_dupli = dob.object
                    if obj_dupli.type == 'MESH':
                        yield (obj_dupli, dob.matrix.copy())

            obj.dupli_list_clear()

    def obj_ray_cast(obj, matrix):
        """Wrapper for ray casting that moves the ray into object space"""

        # get the ray relative to the object
        matrix_inv = matrix.inverted()
        ray_origin_obj = matrix_inv * ray_origin
        ray_target_obj = matrix_inv * ray_target
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
                hit_world = matrix * hit
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
    normal = matrix_new * normal
    normal.normalize()
    
    #####
    profile = findLightGrp(controller).parent
    handle = [ob for ob in profile.children if ob.name.startswith('BLS_HANDLE')][0]
    position = intersect_line_sphere(
        location - handle.location,
        (normal if diff else view_vector.reflect(normal)) + location - handle.location,
        Vector((0,0,0)),
        context.scene.BLStudio.light_radius,
        False,
        )[0]
    
    
    if not position:
        return {'RUNNING_MODAL'}
   
    # ctrl x
    x,y,z = position
    ctrl_x = (degrees(atan2(-x, y)) % 360) * (4/360) -2 +0.015
    
    # ctrl y
    deg = copysign(degrees(Vector.angle(Vector((x,y,z)), Vector((x,y,0)))), z)
    ctrl_y = deg / 90
    
    controller.location.x = ctrl_x
    controller.location.y = ctrl_y

class BLSLightBrush(bpy.types.Operator):
    """Click on object to position light and reflection"""
    bl_idname = "bls.light_brush"
    bl_label = "Light Brush"
    bl_options = {"UNDO"}
    
    pressed = BoolProperty(default=False)
    aux = BoolProperty(default=False) # is aux operator working
    diffuse_type = BoolProperty(default=False)
    
    @classmethod
    def poll(cls, context):
        light = context.scene.objects.active
        return context.area.type == 'VIEW_3D' and \
               context.mode == 'OBJECT' and \
               context.scene.BLStudio.initialized and \
               light and \
               isFamily(light) and \
               not (light.name.startswith('BLS_PANEL') or light.name.startswith('BLS_PROFILE') or light.name.startswith('BLS_LIGHT_GRP'))

    def modal(self, context, event):
        #print(event.type, event.value)
        if self.aux:
            if event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'ESC', 'RET', 'NUMPAD_ENTER'}:
                self.aux = False
            return {'RUNNING_MODAL'}
        
        context.area.header_text_set("[LM] Select Face,  [ESC/RM] Quit,  [N] %s,  [S] Scale, [G] Grab, [R] Rotate" % ('Reflection | [Normal]' if self.diffuse_type else '[Reflection] | Normal'))
        
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'Z', 'LEFT_SHIFT', 'LEFT_ALT', 'LEFT_CTRL'}:
            # allow navigation
            return {'PASS_THROUGH'}
        elif event.type in {'RIGHTMOUSE', 'ESC', 'RET', 'NUMPAD_ENTER'}:
            context.area.header_text_set()
            return {'FINISHED'}
        elif event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                self.pressed = True
                raycast(context, event, self.diffuse_type)
            elif event.value == 'RELEASE':
                self.pressed = False
            return {'RUNNING_MODAL'}
        elif self.pressed and event.type == 'MOUSEMOVE':
            raycast(context, event, self.diffuse_type)
            return {'RUNNING_MODAL'}
        elif event.type == 'S':
            self.aux = True
            bpy.ops.bls.resize_light('INVOKE_DEFAULT')
        elif event.type == 'G':
            self.aux = True
            bpy.ops.bls.move_light('INVOKE_DEFAULT')
        elif event.type == 'R':
            self.aux = True
            bpy.ops.bls.rotate_light('INVOKE_DEFAULT')
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


########################################## Modal AUX Operators ##########################################
from bpy_extras.view3d_utils import location_3d_to_region_2d as loc3d2d
import bgl
def draw_callback_px(self, context): 
    region = context.region  
    rv3d = context.space_data.region_3d
            
    init2d = self.obLoc[:2]
    dest2d = self.mouseCoNew[:2]

    # Line drawing
    bgl.glPushAttrib(bgl.GL_ENABLE_BIT)
    # glPushAttrib is done to return everything to normal after drawing
    
    bgl.glLineStipple(2, 0x9999)
    bgl.glEnable(bgl.GL_LINE_STIPPLE)
    
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glColor4f(0.0, 0.0, 0.0, 1)
    #bgl.glLineWidth(2)

    bgl.glBegin(bgl.GL_LINE_STRIP)
    bgl.glVertex2f(*init2d)
    bgl.glVertex2f(*dest2d)
    bgl.glEnd()
    bgl.glPopAttrib()

    # restore opengl defaults
    bgl.glLineWidth(1)
    bgl.glDisable(bgl.GL_BLEND)
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)

obj_ref = {}
obj_ref['resize'] = None
class BLS_ResizeLight(bpy.types.Operator):
    """Resize BLS Light Mesh"""
    bl_idname = "bls.resize_light"
    bl_label = "Resize BLS Light"
    bl_options = {"REGISTER", "UNDO"}
    
    #mouse and ui
    mouseCo = FloatVectorProperty()
    mouseCoNew = FloatVectorProperty(default=(0,0,0))
    tmp_mouseCo = FloatVectorProperty()
    obLoc = FloatVectorProperty()
    
    #values
    first_value = FloatVectorProperty()
    tmp_value = FloatVectorProperty()
    backup_value = FloatVectorProperty()
    
    #operator dependants
    axis = IntProperty(default=2) # x,y,xy
    precision = BoolProperty()
    
    @classmethod
    def poll(cls, context):
        light = context.scene.objects.active
        return context.area.type == 'VIEW_3D' and \
               context.mode == 'OBJECT' and \
               context.scene.BLStudio.initialized and \
               light and \
               isFamily(light) and \
               not (light.name.startswith('BLS_PANEL') or light.name.startswith('BLS_PROFILE') or light.name.startswith('BLS_LIGHT_GRP'))

    def modal(self, context, event):
        dist2d = lambda p1, p2: sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
        
        if event.type in {'MOUSEMOVE'}:
            region = context.region  
            
            loc2d = [region.width/2, region.height/2]
            #
            self.obLoc = (loc2d[0], loc2d[1], 0)
            
            self.mouseCoNew = Vector((event.mouse_region_x, event.mouse_region_y, 0))
            unit = dist2d(loc2d, self.mouseCo)
            dist = dist2d(loc2d, self.mouseCoNew)
            
            scale = (dist/unit)
            first_scale = Vector(self.first_value)
            
            scale_xyz = first_scale + (first_scale * scale - first_scale) / (10 if self.precision else 1)
            
            if self.axis == 2:
                context.area.header_text_set("Scale X: %.4f Y: %.4f" % (scale, scale))
            elif self.axis == 1:
                scale_xyz[0] = self.first_value[0]
                scale_xyz[2] = self.first_value[2]
                context.area.header_text_set("Scale: %.4f along local Y" % scale)
            elif self.axis == 0:
                scale_xyz[1] = self.first_value[1]
                scale_xyz[2] = self.first_value[2]
                context.area.header_text_set("Scale: %.4f along local X" % scale)
            
            obj_ref['resize'].scale = scale_xyz
            self.tmp_value = scale_xyz
            
            return {'RUNNING_MODAL'}
        elif event.type == 'X' and event.value == 'PRESS':
            self.axis = 0 if self.axis != 0 else 2
        elif event.type == 'Y' and event.value == 'PRESS':
            self.axis = 1 if self.axis != 1 else 2
        elif event.type in {'LEFT_SHIFT', 'RIGHT_SHIFT'}:
             if event.value == 'PRESS':
                 self.precision = True
                 
                 tmp = self.first_value
                 self.first_value = self.tmp_value
                 self.tmp_value = tmp
                 
                 tmp = self.mouseCo
                 self.mouseCo = self.mouseCoNew
                 self.mouseCoNew = tmp
             elif event.value == 'RELEASE':
                 self.precision = False
                 
                 tmp = self.first_value
                 self.first_value = self.tmp_value
                 self.tmp_value = tmp
                 
                 tmp = self.mouseCo
                 self.mouseCo = self.mouseCoNew
                 self.mouseCoNew = tmp
        elif event.type == 'LEFTMOUSE':
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            context.area.header_text_set()
            context.scene.objects.active = context.scene.objects.active
            return {'FINISHED'}
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            obj_ref['resize'].scale = self.backup_value
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            context.area.header_text_set()
            context.scene.objects.active = context.scene.objects.active
            return {'CANCELLED'}
        else:
            #return {'PASS_THROUGH'}
            return {'RUNNING_MODAL'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.space_data.type == 'VIEW_3D':
            self.mouseCo = Vector((event.mouse_region_x, event.mouse_region_y, 0))
            obj_ref['resize'] = getLightController()
            self.first_value = obj_ref['resize'].scale
            self.backup_value = obj_ref['resize'].scale[:]
            args = (self, context)
            self._handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, args, 'WINDOW', 'POST_PIXEL')
            context.window_manager.modal_handler_add(self)
            context.area.header_text_set("Scale X: 1.000 Y: 1.000  [X/Y] Axis, [Shift] Precision mode")
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be a View3d")
            return {'CANCELLED'}
        
obj_ref['move'] = None
class BLS_MoveLight(bpy.types.Operator):
    """Move BLS Light Mesh"""
    bl_idname = "bls.move_light"
    bl_label = "Move BLS Light"
    bl_options = {"REGISTER", "UNDO"}
    
    #mouse and ui
    mouseCo = FloatVectorProperty()
    mouseCoNew = FloatVectorProperty(default=(0,0,0))
    tmp_mouseCo = FloatVectorProperty()
    obLoc = FloatVectorProperty()
    
    #values
    first_value = FloatVectorProperty()
    tmp_value = FloatVectorProperty()
    back_value = FloatVectorProperty()
    
    #operator dependants
    axis = IntProperty(default=2) # [x,y,xy]
    precision = BoolProperty()
    
    @classmethod
    def poll(cls, context):
        light = context.scene.objects.active
        return context.area.type == 'VIEW_3D' and \
               context.mode == 'OBJECT' and \
               context.scene.BLStudio.initialized and \
               light and \
               isFamily(light) and \
               not (light.name.startswith('BLS_PANEL') or light.name.startswith('BLS_PROFILE') or light.name.startswith('BLS_LIGHT_GRP'))

    def modal(self, context, event):
        dist2d = lambda p1, p2: sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
        
        if event.type in {'MOUSEMOVE'}:
            region = context.region  
            rv3d = context.space_data.region_3d
            
            self.mouseCoNew = (event.mouse_region_x, event.mouse_region_y, 0)
            #        
            loc2d = loc3d2d(region, rv3d, self.obLoc)
            dx = self.mouseCoNew[0] - self.mouseCo[0]
            dy = self.mouseCoNew[1] - self.mouseCo[1]
                        
            first_loc = Vector(self.first_value)
            last_loc = Vector((first_loc[0] + dx/(1000 if self.precision else 100), first_loc[1] + dy/(1000 if self.precision else 100), first_loc[2]))
            
            if self.axis == 2: #xy
                context.area.header_text_set("Move Dx: %.4f Dy: %.4f" % (dx, dy))
                last_loc[2] = self.backup_value[2]
            elif self.axis == 1: #y
                last_loc[0] = self.first_value[0]
                last_loc[2] = self.backup_value[2]
                context.area.header_text_set("Move: %.4f along local Y" % dy)
            elif self.axis == 0: #x
                last_loc[1] = self.first_value[1]
                last_loc[2] = self.backup_value[2]
                context.area.header_text_set("Move: %.4f along local X" % dx)
            
            last_loc[0] = (last_loc[0] + 2) % 4 - 2
            obj_ref['move'].location = last_loc
            self.tmp_value = last_loc
            
            return {'RUNNING_MODAL'}
        elif event.type == 'X' and event.value == 'PRESS':
            self.axis = 0 if self.axis != 0 else 2
        elif event.type == 'Y' and event.value == 'PRESS':
            self.axis = 1 if self.axis != 1 else 2
        elif event.type in {'LEFT_SHIFT', 'RIGHT_SHIFT'}:
             if event.value == 'PRESS':
                 self.precision = True
                 
                 tmp = self.first_value
                 self.first_value = self.tmp_value
                 self.tmp_value = tmp
                 
                 tmp = self.mouseCo
                 self.mouseCo = self.mouseCoNew
                 self.mouseCoNew = tmp
             elif event.value == 'RELEASE':
                 self.precision = False
                 
                 tmp = self.first_value
                 self.first_value = self.tmp_value
                 self.tmp_value = tmp
                 
                 tmp = self.mouseCo
                 self.mouseCo = self.mouseCoNew
                 self.mouseCoNew = tmp
        elif event.type == 'LEFTMOUSE':
            context.area.header_text_set()
            return {'FINISHED'}
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            obj_ref['move'].location = self.backup_value
            context.area.header_text_set()
            return {'CANCELLED'}
        else:
            #return {'PASS_THROUGH'}
            return {'RUNNING_MODAL'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.space_data.type == 'VIEW_3D':
            self.mouseCo = Vector((event.mouse_region_x, event.mouse_region_y, 0))
            obj_ref['move'] = getLightController()
            self.first_value = obj_ref['move'].location
            self.backup_value = obj_ref['move'].location[:]
            context.window_manager.modal_handler_add(self)
            context.area.header_text_set("Move Dx: 0.000 Dy: 0.000  [X/Y] Axis, [Shift] Precision mode")
            
            self.obLoc = getLightMesh().matrix_world.to_translation()
            
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be a View3d")
            return {'CANCELLED'}
        
obj_ref['rotate'] = None
class BLS_RotateLight(bpy.types.Operator):
    """Rotate BLS Light Mesh"""
    bl_idname = "bls.rotate_light"
    bl_label = "Rotate BLS Light"
    bl_options = {"REGISTER", "UNDO"}
    
    #mouse and ui
    mouseCo = FloatVectorProperty()
    mouseCoNew = FloatVectorProperty(default=(0,0,0))
    tmp_mouseCo = FloatVectorProperty()
    obLoc = FloatVectorProperty()
    
    #values
    first_value = FloatProperty()
    tmp_value = FloatProperty()
    backup_value = FloatProperty()
    
    #operator dependants
    precision = BoolProperty()
    
    @classmethod
    def poll(cls, context):
        light = context.scene.objects.active
        return context.area.type == 'VIEW_3D' and \
               context.mode == 'OBJECT' and \
               context.scene.BLStudio.initialized and \
               light and \
               isFamily(light) and \
               not (light.name.startswith('BLS_PANEL') or light.name.startswith('BLS_PROFILE') or light.name.startswith('BLS_LIGHT_GRP'))

    def modal(self, context, event):
        dist2d = lambda p1, p2: sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
        
        if event.type in {'MOUSEMOVE'}:
            region = context.region  
            loc2d = [region.width/2, region.height/2]
            self.obLoc = (loc2d[0], loc2d[1], 0)
            #
            self.mouseCoNew = Vector((event.mouse_region_x, event.mouse_region_y, 0))
            angle0 = atan2(self.mouseCo[0] - loc2d[0], self.mouseCo[1] - loc2d[1])
            angle1 = atan2(self.mouseCoNew[0] - loc2d[0], self.mouseCoNew[1] - loc2d[1])
            angle_diff = (angle1 - angle0)
            new_angle = self.first_value + angle_diff
            
            context.area.header_text_set("Rot: {:^0.3f}".format(degrees(angle_diff)))
            
            obj_ref['rotate'].rotation_euler[2] = new_angle
            self.tmp_value = new_angle
            
            return {'RUNNING_MODAL'}
        elif event.type == 'LEFTMOUSE':
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            context.area.header_text_set()
            context.scene.objects.active = context.scene.objects.active
            return {'FINISHED'}
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            obj_ref['rotate'].rotation_euler[2] = self.backup_value
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            context.area.header_text_set()
            context.scene.objects.active = context.scene.objects.active
            return {'CANCELLED'}
        else:
            #return {'PASS_THROUGH'}
            return {'RUNNING_MODAL'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.space_data.type == 'VIEW_3D':
            self.mouseCo = Vector((event.mouse_region_x, event.mouse_region_y, 0))
            obj_ref['rotate'] = getLightController()
            self.first_value = obj_ref['rotate'].rotation_euler[2]
            self.backup_value = obj_ref['rotate'].rotation_euler[2]
            args = (self, context)
            self._handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, args, 'WINDOW', 'POST_PIXEL')
            context.window_manager.modal_handler_add(self)
            context.area.header_text_set("Rot: 0.000")
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be a View3d")
            return {'CANCELLED'}