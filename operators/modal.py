import bpy

from mathutils import *

from . modal_utils import *
from . import *
from .. import light_list

from .modal_utils import shader2Dcolor
from gpu_extras.batch import batch_for_shader
import time, traceback, os
from mathutils.geometry import intersect_line_line_2d
from . import VERBOSE, LightOperator

#textinfo = "[S] Scale | [R] Rotate | [Shift] Precision mode | [Double/Triple Click] Mute, Isolate | [Right Click] Isolate | [+/-] Icon scale | [Ctrl+Click] Loop overlapping"

last_time = time.time()
def draw(self, area):
    if area != bpy.context.area:
        return

    shader2Dcolor.uniform_float("color", (0, 0, 0, 0))
    batch_for_shader(shader2Dcolor, 'POINTS', {"pos": [(0,0), ]}).draw(shader2Dcolor)

    self.panel.draw()
    for b in Button.buttons:
        b.draw(self.mouse_x, self.mouse_y)
    for l in LightImage.lights:
        l.draw()
    
    if VERBOSE:
        font_size = 14
        blf.size(0, font_size, 72)
        excluded = {'click_manager', 'panel', 'handler'}
        for i, kv in enumerate([(k, v) for k, v in self.__dict__.items() if not k in excluded]):
            k, v = kv[:]
            blf.position(0, 55, area.height-115 - (font_size+5)*i, 0)
            blf.draw(0, f'{k}: {v}')


class LLS_OT_Rotate(bpy.types.Operator, MouseWidget, LightOperator):
    bl_idname = "light_studio.rotate"
    bl_label = "Rotate Light"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def __init__(self):
        super().__init__()
        # self.pivot = Vector((self.mouse_x, self.mouse_y))
        self.base_object_rotation = 0
        self.allow_precision_mode = True

    def invoke(self, context, event):
        global running_modals
        if running_modals:
            active_object = LightImage.selected_object
            self.mouse_x=active_object.loc.x
            self.mouse_y=active_object.loc.y
        else:
            # override starting mouse position
            self.mouse_x = context.area.width/2
            self.mouse_y = context.area.height/2
        super().invoke(context, event)

        if running_modals:
            self.base_object_rotation = LightImage.selected_object._lls_handle.rotation_euler.y
        else:
            self.base_object_rotation = context.object.parent.rotation_euler.y

        return {"RUNNING_MODAL"}
    
    def _finish(self, context, event):
        bpy.context.workspace.status_text_set(None)
        #context.area.header_text_set(text=None)

    def _cancel(self, context, event):
        global running_modals
        if running_modals:
            LightImage.selected_object._lls_handle.rotation_euler.y = self.base_object_rotation
        else:
            context.object.parent.rotation_euler.y = self.base_object_rotation

        bpy.context.workspace.status_text_set(None)
        #context.area.header_text_set(text=None)

    def _modal(self, context, event):
        global running_modals
        if running_modals:
            LightImage.selected_object._lls_handle.rotation_euler.y = self.base_object_rotation + self.angle()
        else:
            context.object.parent.rotation_euler.y = self.base_object_rotation + self.angle()

        bpy.context.workspace.status_text_set(f"Rot: {self.angle():.3f}")
        #context.area.header_text_set(text=f"Rot: {self.angle():.3f}")

        if not event.type in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
            return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}

def get_scale_adapter(light_object):
    if light_object.type == 'MESH':
        return light_object.scale.copy()
    elif light_object.type == 'LIGHT':
        return Vector((light_object.data.size / 9, light_object.data.size / 9, light_object.data.size_y / 9))

def set_scale_adapter(light_object, new_scale):
    if light_object.type == 'MESH':
        light_object.scale = new_scale
    elif light_object.type == 'LIGHT':
        light_object.data.size = new_scale.y * 9
        light_object.data.size_y = new_scale.z * 9

class LLS_OT_Scale(bpy.types.Operator, MouseWidget, LightOperator):
    bl_idname = "light_studio.scale"
    bl_label = "Scale Light"
    bl_options = {"GRAB_CURSOR", "BLOCKING", "REGISTER", "UNDO", "INTERNAL"}

    def __init__(self):
        super().__init__()
        self.pivot = Vector((self.mouse_x, self.mouse_y))
        self.base_object_scale = 0
        self.allow_xy_keys = True
        self.allow_precision_mode = True

    def invoke(self, context, event):
        global running_modals
        if running_modals:
            active_object = LightImage.selected_object
            self.mouse_x=active_object.loc.x
            self.mouse_y=active_object.loc.y
        else:
            # override starting mouse position
            self.mouse_x = context.area.width/2
            self.mouse_y = context.area.height/2
        super().invoke(context, event)
        
        if running_modals:
            self.base_object_scale = LightImage.selected_object.light_scale.copy()
        else:
            self.base_object_scale = get_scale_adapter(context.object)
        return {"RUNNING_MODAL"}
    
    def _cancel(self, context, event):
        global running_modals
        if running_modals:
            LightImage.selected_object.light_scale = self.base_object_scale
        else:
            # context.object.scale = self.base_object_scale
            set_scale_adapter(context.object, self.base_object_scale)
        bpy.context.workspace.status_text_set(None)
        #context.area.header_text_set(text=None)

    def _finish(self, context, event):
        bpy.context.workspace.status_text_set(None)
        #context.area.header_text_set(text=None)

    def _modal(self, context, event):
        new_scale = self.base_object_scale * self.delta_length_factor()
        if self.x_key:
            new_scale.z = self.base_object_scale.z
        if self.y_key:
            new_scale.y = self.base_object_scale.y

        global running_modals
        if running_modals:
            LightImage.selected_object.light_scale = new_scale
        else:
            set_scale_adapter(context.object, new_scale)
        bpy.context.workspace.status_text_set(f"Scale X: {new_scale.y:.3f} Y: {new_scale.z:.3f}  [X/Y] Axis, [Shift] Precision mode")
        #context.area.header_text_set(text=f"Scale X: {new_scale.y:.3f} Y: {new_scale.z:.3f}  [X/Y] Axis, [Shift] Precision mode")

        if event.value == "PRESS" and not event.type in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
            return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}

GRABBING = False
class LLS_OT_Grab(bpy.types.Operator, MouseWidget, LightOperator):
    bl_idname = "light_studio.grab"
    bl_label = "Grab Light"
    bl_options = {"UNDO", "GRAB_CURSOR", "BLOCKING", "INTERNAL"}


    def __init__(self):
        super().__init__()
        self.pivot = Vector((self.mouse_x, self.mouse_y))
        self.base_object_rotation = Vector((0, 0, 0))
        self.allow_xy_keys = True
        self.continous = True
        self.draw_guide = False
        self.allow_precision_mode = True
        self.precision_factor = 0.05
        self.canvas_width = 1
        self.canvas_height = 1


    def invoke(self, context, event):
        global running_modals

        if running_modals:
            # override starting mouse position
            global panel_global
            self.mouse_x = LightImage.selected_object.loc.x
            self.mouse_y = LightImage.selected_object.loc.y
            self.light_object = LightImage.selected_object._lls_object
            self.light_actuator = LightImage.selected_object._lls_actuator
            self.base_object_rotation = self.light_actuator.rotation_euler.copy()
            self.base_object_distance = self.light_object.location.x
            self.canvas_width = panel_global.width
            self.canvas_height = panel_global.height
        else:
            # override starting mouse position
            self.mouse_x = context.area.width/2
            self.mouse_y = context.area.height/2
            self.light_actuator = context.object.parent.parent
            self.light_object = context.object.parent
            self.base_object_rotation = context.object.parent.parent.rotation_euler.copy()
            self.base_object_distance = context.object.parent.location.x
        super().invoke(context, event)
        return {"RUNNING_MODAL"}
    
    def _cancel(self, context, event):
        global running_modals
        self.light_actuator.rotation_euler = self.base_object_rotation
        self.light_object.location.x = self.base_object_distance
        
        global GRABBING
        GRABBING = False
        bpy.context.workspace.status_text_set(None)
        #context.area.header_text_set(text=None)

    def _finish(self, context, event):
        global GRABBING
        GRABBING = False
        bpy.context.workspace.status_text_set(None)
        #context.area.header_text_set(text=None)

    def _modal(self, context, event):
        dv = self.delta_vector()
        if self.x_key:
            dv.y = 0
        elif self.y_key:
            dv.x = 0

        global running_modals
        if running_modals:
            x_factor = 2*pi / self.canvas_width
            y_factor = pi / self.canvas_height
        else:
            x_factor = .0025 #2*pi / 500
            y_factor = .0025 #pi / 250

        if self.z_key:
            self.light_object.location.x = max(self.base_object_distance + dv.x * 0.05, 0)
            import bpy_extras
            self.z_start_position = bpy_extras.view3d_utils.location_3d_to_region_2d(context.region, context.space_data.region_3d, self.light_object.matrix_world.to_translation().normalized() * context.space_data.clip_end)
            self.z_end_position = bpy_extras.view3d_utils.location_3d_to_region_2d(context.region, context.space_data.region_3d, Vector((0,0,0)))
            if running_modals:
                global panel_global
                v1 = panel_global.point_lt
                v2 = Vector((panel_global.point_rb.x, panel_global.point_lt.y))
                v3 = panel_global.point_rb
                v4 = Vector((panel_global.point_lt.x, panel_global.point_rb.y))
                lines = [(v1, v2), (v2, v3), (v3, v4), (v1, v4)]
                shortest = None
                for v1, v2 in lines:
                    intersection = intersect_line_line_2d(self.z_start_position, self.z_end_position, v1, v2)
                    if intersection:
                        length = (self.z_start_position - intersection).length
                        if not shortest or length < shortest:
                            shortest = length
                            self.z_end_position = intersection

        else:
            self.light_actuator.rotation_euler = self.base_object_rotation.copy()
            self.light_actuator.rotation_euler.x += dv.x * x_factor
            self.light_actuator.rotation_euler.y += dv.y * y_factor
            self.light_actuator.rotation_euler.y = clamp(-pi/2 + 0.000001, self.light_actuator.rotation_euler.y, pi/2 - 0.000001)

        bpy.context.workspace.status_text_set(f"Move Dx: {dv.x * x_factor:.3f} Dy: {dv.y * y_factor:.3f}   [X/Y] Axis  [Z] Distance  [Shift] Precision Mode")
        #context.area.header_text_set(text=f"Move Dx: {dv.x * x_factor:.3f} Dy: {dv.y * y_factor:.3f}   [X/Y] Axis | [Shift] Precision Mode")

        if event.value == "PRESS" and not event.type in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
            return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}

from bpy.app.handlers import persistent
@persistent
def load_handler(dummy):
    global running_modals
    running_modals = 0

scene_before_frame_change = None
@persistent
def frame_change_handler(scene):
    global panel_global
    global running_modals
    global scene_before_frame_change
    if running_modals and panel_global and scene.name != scene_before_frame_change:
        update_light_sets(panel_global, bpy.context, always=True)
        scene_before_frame_change = scene.name

panel_global = None
running_modals = 0
W_LEFT = 1
W_RIGHT = 2
W_TOP = 4
W_BOTTOM = 8
class LLS_OT_control_panel(bpy.types.Operator):
    bl_idname = "light_studio.control_panel"
    bl_label = "LightStudio Control Panel"
    bl_description = "Show/Hide LightStudio Control Panel"

    mouse_x: bpy.props.IntProperty()
    mouse_y: bpy.props.IntProperty()

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and context.scene.LLStudio.initialized

    def __init__(self):
        self.handler = None
        self.panel = None
        self.panel_moving = False
        self.clicked_object = None
        self.click_manager = ClickManager()
        self.active_feature = None
        self.precision_mode = False
        self.border_touch = 0
        self.modifier_key = False
        self.ctrl = False

    def __del__(self):
        if VERBOSE: print("Panel __del__")
        self._unregister_handler()

    def _unregister_handler(self):
        global running_modals
        running_modals = max(0, running_modals-1)
        try:
            if hasattr(self, 'handler'):
                bpy.types.SpaceView3D.draw_handler_remove(self.handler, 'WINDOW')
        except (ValueError, AttributeError):
            # if VERBOSE: traceback.print_exc()
            pass

    def _mouse_event(self, context, event):
        area_mouse_x = event.mouse_x - context.area.x
        area_mouse_y = event.mouse_y - context.area.y
        dx = area_mouse_x - self.mouse_x
        dy = area_mouse_y - self.mouse_y
        self.mouse_x = area_mouse_x
        self.mouse_y = area_mouse_y
        return dx, dy, area_mouse_x, area_mouse_y

    def invoke(self, context, event):
        light_list.update_light_list_set(context)

        global running_modals
        running_modals += 1
        if running_modals > 1:
            # toggle panel
            running_modals = 0
            return {"CANCELLED"}

        self.handler = bpy.types.SpaceView3D.draw_handler_add(draw, (self, context.area), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        aw = context.area.width
        ah = context.area.height
        pw = min(aw-60, 800)
        
        global panel_global
        if not panel_global:
            panel_global = Panel(Vector((30, 25)), pw, pw*(9/16))
        self.panel = panel_global

        LightImage.default_size = 50

        self.mouse_x = event.mouse_x - context.area.x
        self.mouse_y = event.mouse_y - context.area.y

        update_light_sets(self.panel, context, always=True)
        #bpy.context.workspace.status_text_set(textinfo)
        #context.area.header_text_set(text=textinfo)

        self.ctrl = False
        self.modifier_key = False

        return {"RUNNING_MODAL"}
    
    def border_touch_point(self, context, area_mouse_x, area_mouse_y):
        touch_point = 0
        treshold = 5

        # decrease clickable size by UI tools region
        r_ui = [r for r in context.area.regions if r.type == 'UI'][0]
        if r_ui.alignment=='RIGHT':
            if area_mouse_x >= context.area.width - r_ui.width - 2:
                return touch_point
        else:
            if area_mouse_x <= r_ui.width + 2:
                return touch_point


        for b in Button.buttons:
            if is_in_rect(b, Vector((area_mouse_x, area_mouse_y))):
                context.window.cursor_set('DEFAULT')
                return 0

        if area_mouse_y >= self.panel.point_rb.y-treshold and area_mouse_y <= self.panel.point_lt.y+treshold:
            if area_mouse_x < self.panel.point_lt.x+treshold and area_mouse_x >= self.panel.point_lt.x-treshold:
                touch_point |= W_LEFT
                context.window.cursor_set('MOVE_X')
            elif area_mouse_x > self.panel.point_rb.x-treshold and area_mouse_x <= self.panel.point_rb.x+treshold:
                touch_point |= W_RIGHT
                context.window.cursor_set('MOVE_X')
        
        if area_mouse_x >= self.panel.point_lt.x-treshold and area_mouse_x <= self.panel.point_rb.x+treshold:
            if area_mouse_y > self.panel.point_lt.y-treshold and area_mouse_y <= self.panel.point_lt.y+treshold:
                touch_point |= W_TOP
                context.window.cursor_set('MOVE_Y')
            elif area_mouse_y < self.panel.point_rb.y+treshold and area_mouse_y >= self.panel.point_rb.y-treshold:
                touch_point |= W_BOTTOM
                context.window.cursor_set('MOVE_Y')

        if touch_point == W_LEFT | W_TOP\
            or touch_point == W_LEFT | W_BOTTOM\
            or touch_point == W_RIGHT | W_TOP\
            or touch_point == W_RIGHT | W_BOTTOM:
            context.window.cursor_set('SCROLL_XY')
        elif touch_point == 0:
            context.window.cursor_set('DEFAULT')
        
        return touch_point

    def modal(self, context, event):
        global running_modals
        if running_modals < 1:
            self._unregister_handler()
            context.area.tag_redraw()
            return {"FINISHED"}

        # if event.type != "MOUSEMOVE":
        #     print(event.type, event.value)

        if not context.area or (context.object and not context.object.mode == 'OBJECT'):
            self._unregister_handler()
            return {"CANCELLED"}
        try:
            context.area.tag_redraw()

            update_light_sets(self.panel, context)
            LightImage.refresh()

            if event.type in {"TIMER", "NONE", "WINDOW_DEACTIVATE"}:
                self.ctrl = False
                self.modifier_key = False
            elif event.type in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
                dx, dy, area_mouse_x, area_mouse_y = self._mouse_event(context, event)
                
                # Draw resize cursor
                touch_point = self.border_touch_point(context, area_mouse_x, area_mouse_y)
                if self.border_touch and event.value == "PRESS":
                    if self.border_touch & W_LEFT:
                        self.panel.point_lt.x = min(area_mouse_x, self.panel.point_rb.x - 100)
                    elif self.border_touch & W_RIGHT:
                        self.panel.point_rb.x = max(area_mouse_x, self.panel.point_lt.x + 100)
                    if self.border_touch & W_TOP:
                        self.panel.point_lt.y = max(area_mouse_y, self.panel.point_rb.y + 100)
                    elif self.border_touch & W_BOTTOM:
                        self.panel.point_rb.y = min(area_mouse_y, self.panel.point_lt.y - 100)
                    self.panel.move(Vector([0,0]))

                if self.clicked_object and self.panel_moving:
                    if isinstance(self.clicked_object, Panel):
                        self.clicked_object.move(Vector((dx * (.1 if self.precision_mode else 1), dy * (.1 if self.precision_mode else 1))))
                    elif isinstance(self.clicked_object, Button):
                        pass
                    else:
                        active_object = LightImage.selected_object
                        if active_object and not GRABBING:
                            bpy.ops.light_studio.grab('INVOKE_DEFAULT', mouse_x=active_object.loc.x, mouse_y=active_object.loc.y)
                            self.panel_moving = False                    
                    
                    return {"RUNNING_MODAL"}

                return {"PASS_THROUGH"}
            
            if event.value == "PRESS":
                if event.type in {"LEFT_CTRL", "RIGHT_CTRL", "LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_ALT", "RIGHT_ALT"}:
                    self.modifier_key = True
                if event.type in {"LEFT_CTRL"}:
                    self.ctrl = True

                elif event.type == "RIGHTMOUSE":
                    dx, dy, area_mouse_x, area_mouse_y = self._mouse_event(context, event)
                    self.clicked_object = self.find_clicked(area_mouse_x, area_mouse_y)

                    if not self.clicked_object:
                        return {"PASS_THROUGH"}
                    
                    if hasattr(self.clicked_object, 'mute'):
                        muted_count = len([l for l in LightImage.lights if l.mute])
                        unmuted_count = len(LightImage.lights) - muted_count
                        if muted_count == 0:
                            # no muted at start. mute all but selected
                            for l in LightImage.lights:
                                l.mute = True
                            self.clicked_object.mute = False
                        else:
                            # some muted.
                            if unmuted_count == 1 and self.clicked_object.mute == False:
                                for l in LightImage.lights:
                                    l.mute = False
                            else:
                                for l in LightImage.lights:
                                    l.mute = True
                                self.clicked_object.mute = False

                    if hasattr(self.clicked_object, 'select'):
                        self.clicked_object.select()
                    
                    return {"RUNNING_MODAL"}

                # Left mouse button pressed            
                elif event.type == "LEFTMOUSE":
                    dx, dy, area_mouse_x, area_mouse_y = self._mouse_event(context, event)

                    overlapped = self.find_clicked(area_mouse_x, area_mouse_y, overlapping=True)
                    if type(overlapped) == list:
                        # List of overlapping lights
                        self.clicked_object = overlapped[0] if overlapped else None
                    else:
                        # Button
                        self.clicked_object = overlapped

                    # Resize
                    # Find border touch point. 0 when no point found
                    touch_point = self.border_touch_point(context, area_mouse_x, area_mouse_y)
                    # Make sure border touch point is not obstructed by other objects
                    if touch_point and not isinstance(self.clicked_object, Button):
                        self.border_touch = touch_point
                        return {"RUNNING_MODAL"}
                    
                    self.panel_moving = self.clicked_object != None

                    click_result = self.click_manager.click(self.clicked_object)
                    if not self.ctrl and hasattr(self.clicked_object, 'mute'):
                        if click_result == "TRIPLE":
                            muted_count = len([l for l in LightImage.lights if l.mute]) - 1
                            unmuted_count = len(LightImage.lights) - muted_count
                            if muted_count == 0:
                                # no muted at start. mute all but selected
                                for l in LightImage.lights:
                                    l.mute = True
                                self.clicked_object.mute = False
                            else:
                                # some muted.
                                if unmuted_count == 1 and self.clicked_object.mute == True:
                                    for l in LightImage.lights:
                                        l.mute = False
                                else:
                                    for l in LightImage.lights:
                                        l.mute = True
                                    self.clicked_object.mute = False
                        elif click_result == "DOUBLE":
                            self.clicked_object.mute = not self.clicked_object.mute

                    if hasattr(self.clicked_object, 'select'):
                        try:
                            self.clicked_object.select()
                        except RuntimeError:
                            print("Stale panel context. Reloaded.")
                            # close_control_panel()
                            update_light_sets(self.panel, context, always=True)
                            if VERBOSE: traceback.print_exc()
                        else:
                            if self.ctrl and len(overlapped)>1:
                                send_light_to_bottom(self.clicked_object)
                                self.find_clicked(area_mouse_x, area_mouse_y).select()
                            else:
                                send_light_to_top(self.clicked_object)


                    if hasattr(self.clicked_object, 'click'):
                        result = self.clicked_object.click()
                        if result == "FINISHED":
                            bpy.context.workspace.status_text_set(None) #clear help if window is closed
                            #context.area.header_text_set(text=None)
                            self._unregister_handler()
                            return {"FINISHED"}
                        return {"RUNNING_MODAL"}

                    if self.clicked_object:
                        return {"RUNNING_MODAL"}
                    return {"PASS_THROUGH"}

                elif event.type == "NUMPAD_PLUS":
                    LightImage.change_default_size(LightImage.default_size+10)
                    return {'RUNNING_MODAL'}
                elif event.type == "NUMPAD_MINUS":
                    LightImage.change_default_size(LightImage.default_size-10)
                    return {'RUNNING_MODAL'}
                elif event.type == "LEFT_SHIFT":
                    self.precision_mode = True
                    return {'RUNNING_MODAL'}
                
                # Return (Enter) key is pressed
                elif event.type == "RET":
                    bpy.context.workspace.status_text_set(None)
                    #context.area.header_text_set(text=None)
                    self._unregister_handler()
                    return {'FINISHED'}
            
            if event.value == "RELEASE":
                #bpy.context.workspace.status_text_set(textinfo)
                #context.area.header_text_set(text=textinfo)
                if event.type in {"LEFT_CTRL", "RIGHT_CTRL", "LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_ALT", "RIGHT_ALT"}:
                    self.modifier_key = False
                if event.type == "LEFTMOUSE":
                    self.panel_moving = False
                    self.border_touch = 0
                elif event.type == "LEFT_SHIFT":
                    self.precision_mode = False
                    return {'RUNNING_MODAL'}
            elif event.value == "CLICK":
                # Left mouse button clicked
                if event.type == "LEFTMOUSE":
                    return {"PASS_THROUGH"}
        except:
            self._unregister_handler()
            if VERBOSE: traceback.print_exc()
            return {"CANCELLED"}
        
        return {"PASS_THROUGH"}

    def find_clicked(self, area_mouse_x, area_mouse_y, overlapping=False):
        # decrease clickable size by UI tools region
        r_ui = [r for r in bpy.context.area.regions if r.type == 'UI'][0]
        if r_ui.alignment=='RIGHT':
            if area_mouse_x >= bpy.context.area.width - r_ui.width - 2:
                return None
        else:
            if area_mouse_x <= r_ui.width + 2:
                return None

        
        overlapped = []
        for l in reversed(LightImage.lights):
            if l.is_mouse_over(area_mouse_x, area_mouse_y):
                if not overlapping:
                    return l
                else:
                    overlapped.append(l)

        if overlapping and overlapped:
            return overlapped
        
        for b in Button.buttons:
            if is_in_rect(b, Vector((area_mouse_x, area_mouse_y))):
                return b

        if is_in_rect(self.panel, Vector((area_mouse_x, area_mouse_y))):
            return self.panel
        return None

from .. light_data import salvage_data, convert_old_light, light_from_dict
def update_light_sets(panel, context, always=False):
    lls_collection, profile_collection = llscol_profilecol(context)
    if profile_collection is not None:
        if is_updated() or always or len(profile_collection.children) != len(LightImage.lights):
            lls_lights = set(profile_collection.children)
            working_set = set((l._collection for l in LightImage.lights))

            to_delete = working_set.difference(lls_lights)
            to_add =  lls_lights.difference(working_set)
            
            for col in to_delete:
                LightImage.remove(col)

            for col in to_add:
                try:
                    LightImage(context, panel, col)
                except:
                    # Salvage data
                    objects = [ob for ob in col.objects]
                    light_root = [ob for ob in objects if ob.name.startswith("LLS_LIGHT.")]
                    if light_root:
                        light_root = light_root[0]
                        # convert_old_light(light_root, profile_collection)

                    family_obs = family(light_root)


                    light = salvage_data(col)

                    # Some crucial objects are missing. Delete whole light collection
                    # bpy.ops.object.delete({"selected_objects": col.objects}, use_global=True)
                    bpy.ops.object.delete({"selected_objects": list(family_obs)}, use_global=True)
                    bpy.data.collections.remove(col)
                    
                    # override = context.copy()
                    # override['selected_objects'] = col.objects
                    # bpy.ops.object.delete_custom(override, use_global=True)

                    light_from_dict(light, profile_collection)

            update_clear()

def close_control_panel():
    global running_modals
    running_modals = 0

addon_keymaps = []
def add_shortkeys():
    wm = bpy.context.window_manager
    addon_km = wm.keyconfigs.addon.keymaps.new(name='Object Mode', space_type="EMPTY")

    addon_kmi = addon_km.keymap_items.new(LLS_OT_Grab.bl_idname, 'G', 'PRESS')
    addon_keymaps.append((addon_km, addon_kmi))

    addon_kmi = addon_km.keymap_items.new(LLS_OT_Scale.bl_idname, 'S', 'PRESS')
    addon_keymaps.append((addon_km, addon_kmi))

    addon_kmi = addon_km.keymap_items.new(LLS_OT_Rotate.bl_idname, 'R', 'PRESS')
    addon_keymaps.append((addon_km, addon_kmi))

def remove_shortkeys():
    wm = bpy.context.window_manager
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
        
    addon_keymaps.clear()