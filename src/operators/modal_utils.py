import gpu, bgl, blf
from gpu_extras.batch import batch_for_shader
from mathutils import *
from math import pi, fmod, radians, sin, cos, atan2
from .. common import *
from . import *
import time
from copy import deepcopy

shader2Dcolor = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
shader2Dcolor.bind()

vertex_shader = '''
    uniform mat4 ModelViewProjectionMatrix;

    /* Keep in sync with intern/opencolorio/gpu_shader_display_transform_vertex.glsl */
    in vec2 pos;
    in vec2 texCoord;
    out vec2 texCoord_interp;

    void main()
    {
        gl_Position = ModelViewProjectionMatrix * vec4(pos.xy, 0.0f, 1.0f);
        gl_Position.z = 1.0;
        texCoord_interp = texCoord;
    }
'''

fragment_shader = '''
    #define PI 3.1415926535897932384626433832795f

    in vec2 texCoord_interp;
    in vec4 gl_FragCoord;

    layout(location = 0) out vec4 fragColor;
    layout(location = 1) out vec4 trash;

    uniform sampler2D image;
    uniform vec2 panel_point_lt;
    uniform vec2 panel_point_rb;

    uniform vec4 color_overlay = vec4(0);
    uniform float intensity = 1;
    uniform float texture_switch = 1;
    uniform float color_saturation = 0;

    uniform float mask_bottom_to_top = 0;
    uniform float mask_diagonal_bottom_left = 0;
    uniform float mask_diagonal_bottom_right = 0;
    uniform float mask_diagonal_top_left = 0;
    uniform float mask_diagonal_top_right = 0;
    uniform float mask_gradient_amount = 0;
    uniform float mask_gradient_switch = 0;
    uniform float mask_gradient_type = 0;
    uniform float mask_left_to_right = 0;
    uniform float mask_right_to_left = 0;
    uniform float mask_ring_inner_radius = 0;
    uniform float mask_ring_outer_radius = 0;
    uniform float mask_ring_switch = 0;
    uniform float mask_top_to_bottom = 0;

    void main()
    {
        // Trash output - sum all uniforms to prevent compiler from skipping currently unused ones
        trash = vec4(panel_point_lt.x+panel_point_rb.x+mask_bottom_to_top+mask_diagonal_bottom_left+mask_diagonal_bottom_right+mask_diagonal_top_left+mask_diagonal_top_right+mask_gradient_amount+mask_gradient_switch+mask_gradient_type+mask_left_to_right+mask_right_to_left+mask_ring_inner_radius+mask_ring_outer_radius+mask_ring_switch+mask_top_to_bottom);

        // Texture Switch + Intensity
        // log(1+intensity) so the images won't get overexposed too fast when high intensity values used
        fragColor = mix(vec4(1.0f), texture(image, texCoord_interp), texture_switch) * log(1+intensity);

        // Color Overlay
        float gray = clamp(dot(fragColor.rgb, vec3(0.299, 0.587, 0.114)), 0, 1);
        vec4 colored = color_overlay * gray;

        // Color Saturation
        fragColor = mix(fragColor, colored, color_saturation);
        fragColor.a = gray;
        fragColor.rgb *= fragColor.a;

        // MASKS //

        // Vertical gradient + mask_gradient_amount
        float vg = sqrt(texCoord_interp.y);
        vg = (texCoord_interp.y <= mask_gradient_amount+.05f) ? mix(0, vg, (texCoord_interp.y-mask_gradient_amount)/.05f) : vg;
        vg = texCoord_interp.y >= mask_gradient_amount ? vg : 0;

        // Spherical gradient + mask_gradient_amount
        float d = distance(texCoord_interp.xy, vec2(0.5f, 0.5f));
        float m = (1.0f-mask_gradient_amount)*.5f;
        float sg = 1-pow(d*2, 2.f);
        sg = (d >= m-.05f) ? mix(0, sg, (m-d)/.05f) : sg;
        sg = (d <= m) ? sg : 0;

        // Gradient Type
        float grad = mix(sg, vg, mask_gradient_type);

        // Gradient Switch
        fragColor.a = mix(fragColor.a, grad*fragColor.a, mask_gradient_switch);

        // Gradient Ring Switch
        float ring = d < (1-mask_ring_outer_radius)*.575f ? 1 : 0;
        ring = d < (1-mask_ring_inner_radius)*.55f ? 0 : ring;
        fragColor.a = mix(fragColor.a, fragColor.a*ring, mask_ring_switch);

        // Top-Bottom
        fragColor.a = texCoord_interp.y < (1-mask_top_to_bottom) ? fragColor.a : 0;

        // Bottom-Top
        fragColor.a = texCoord_interp.y > mask_bottom_to_top ? fragColor.a : 0;

        // Left-Right
        fragColor.a = texCoord_interp.x > mask_left_to_right ? fragColor.a : 0;

        // Right-Left
        fragColor.a = texCoord_interp.x < (1-mask_right_to_left) ? fragColor.a : 0;

        // Diagonal Top-Right
        fragColor.a = 1-(texCoord_interp.x+texCoord_interp.y)/2 > mask_diagonal_top_right ? fragColor.a : 0;

        // Diagonal Top-Left
        fragColor.a = 1-(1-texCoord_interp.x+texCoord_interp.y)/2 > mask_diagonal_top_left ? fragColor.a : 0;

        // Diagonal Bottom-Right
        fragColor.a = (1-texCoord_interp.x+texCoord_interp.y)/2 > mask_diagonal_bottom_right ? fragColor.a : 0;

        // Diagonal Bottom-Left
        fragColor.a = (texCoord_interp.x+texCoord_interp.y)/2 > mask_diagonal_bottom_left ? fragColor.a : 0;

        // Panel bound clipping
        if((gl_FragCoord.x < panel_point_lt.x || gl_FragCoord.x > panel_point_rb.x)
         || (gl_FragCoord.y < panel_point_rb.y || gl_FragCoord.y > panel_point_lt.y))
            discard;
    }
'''

border_vertex_shader= '''
    uniform mat4 ModelViewProjectionMatrix;

    #ifdef UV_POS
    in vec2 u;
    #  define pos u
    #else
    in vec2 pos;
    #endif

    void main()
    {
        gl_Position = ModelViewProjectionMatrix * vec4(pos, 0.0, 1.0);
    }
'''
border_fragment_shader= '''
    uniform vec4 color;
    uniform vec2 panel_point_lt;
    uniform vec2 panel_point_rb;
    in vec4 gl_FragCoord;
    out vec4 fragColor;

    void main()
    {
        fragColor = color;

        if((gl_FragCoord.x < panel_point_lt.x || gl_FragCoord.x > panel_point_rb.x)
         || (gl_FragCoord.y < panel_point_rb.y || gl_FragCoord.y > panel_point_lt.y))
            discard;
    }
'''

lightIconShader = gpu.types.GPUShader(vertex_shader, fragment_shader)
lightIconShader.bind()

border_shader2Dcolor = gpu.types.GPUShader(border_vertex_shader, border_fragment_shader)
border_shader2Dcolor.bind()

class Rectangle:
    def __init__(self, start_point, width, height):
        self.point_lt = Vector((
            min(start_point.x, start_point.x+width),
            max(start_point.y, start_point.y+height),
            ))
        self.point_rb = Vector((
            max(start_point.x, start_point.x+width),
            min(start_point.y, start_point.y+height),
            ))

        self.rot = 0

    @property
    def loc(self):
        return (self.point_lt + self.point_rb)/2

    @loc.setter
    def loc(self, loc):
        d = loc - self.loc
        self.point_lt += d
        self.point_rb += d

    @property
    def width(self):
        return self.point_rb.x - self.point_lt.x

    @width.setter
    def width(self, width):
        d = width - self.width
        self.point_lt.x -= d/2
        self.point_rb.x = self.point_lt.x + width

    @property
    def height(self):
        return self.point_lt.y - self.point_rb.y

    @height.setter
    def height(self, height):
        d = height - self.height
        self.point_lt.y += d/2
        self.point_rb.y = self.point_lt.y - height

    def get_verts(self):
        def rotate(x1, y1, offset):
            x1 -= offset.x
            y1 -= offset.y
            x2 = cos(self.rot) * x1 - sin(self.rot) * y1
            y2 = sin(self.rot) * x1 + cos(self.rot) * y1
            x2 += offset.x
            y2 += offset.y
            return [x2, y2]

        loc = self.loc # prevent property from recomputing
        return (
            rotate(self.point_lt.x, self.point_lt.y, loc),
            rotate(self.point_lt.x, self.point_rb.y, loc),
            rotate(self.point_rb.x, self.point_lt.y, loc),
            rotate(self.point_rb.x, self.point_rb.y, loc),
        )

    def get_tex_coords(self):
        return ([0, 1], [0, 0], [1, 1], [1, 0])

    def move(self, loc_diff):
        rect = self.panel if hasattr(self, 'panel') else self

        new_loc = self.loc + loc_diff
        new_loc.x = clamp(rect.point_lt.x, new_loc.x, rect.point_rb.x)
        new_loc.y = clamp(rect.point_rb.y, new_loc.y, rect.point_lt.y)
        self.loc = new_loc

def send_light_to_bottom(light=None):
    light = LightImage.selected_object if not light else light
    if not light:
        return
    lights = LightImage.lights
    lights.insert(0, lights.pop(lights.index(light)))

def send_light_to_top(light=None):
    light = LightImage.selected_object if not light else light
    if not light:
        return
    lights = LightImage.lights
    lights.append(lights.pop(lights.index(light)))

def fast_3d_edit(light=None):
    try:
        bpy.ops.light_studio.fast_3d_edit('INVOKE_DEFAULT', continuous=False)
    except:
        pass

from .. common import get_user_keymap_item
from .. light_brush import OT_LLSFast3DEdit
class Panel(Rectangle):
    def __init__(self, loc, width, height):
        super().__init__(loc, width, height)
        self.button_exit = Button(Vector((0,0)), 'X')
        self.button_exit.function = lambda x: "FINISHED"

        self.button_send_to_bottom = Button(Vector((0,0)), 'Send to Bottom')
        self.button_send_to_bottom.function = send_light_to_bottom

        km, kmi = get_user_keymap_item('Object Mode', OT_LLSFast3DEdit.bl_idname)
        self.button_fast_3d_edit = Button(Vector((0,0)), f'Light Brush [{kmi.type}]')
        self.button_fast_3d_edit.function = fast_3d_edit

        self._move_buttons()

    def _move_buttons(self):
        self.button_exit.loc = Vector((
            self.point_rb.x - self.button_exit.dimensions[0]/4,
            self.point_lt.y - self.button_exit.dimensions[1]/4+3,
        ))

        self.button_send_to_bottom.loc = Vector((
            self.point_lt.x + self.button_send_to_bottom.dimensions[0]/2 + 5,
            self.point_rb.y - self.button_exit.dimensions[1]/2 - 10,
        ))

        self.button_fast_3d_edit.loc = Vector((
            self.point_lt.x + self.button_send_to_bottom.dimensions[0] + self.button_fast_3d_edit.dimensions[0]/2 + 23,
            self.point_rb.y - self.button_exit.dimensions[1]/2 - 10,
        ))

    def draw(self):
        shader2Dcolor.uniform_float("color", (0.05, 0.05, 0.05, 1))
        batch_for_shader(shader2Dcolor, 'TRI_STRIP', {"pos": self.get_verts()}).draw(shader2Dcolor)

    def move(self, loc_diff):
        super().move(loc_diff)

        for l in LightImage.lights:
            l.update_visual_location()

        self._move_buttons()

class Button(Rectangle):
    buttons = []
    def __init__(self, loc, text, size=15):
        self.font_size = size
        self.font_color = (0, 0, 0, 1)
        self.bg_color = (.5, .5, .5, 1)
        self.bg_color_selected = (.7, .7, .7, 1)
        self.font_id = len(Button.buttons)
        self.text = text
        blf.color(self.font_id, *self.font_color)
        blf.position(self.font_id, *loc, 0)
        blf.size(self.font_id, self.font_size, 72)
        self.dimensions = blf.dimensions(self.font_id, text)
        self.function = lambda args : None

        super().__init__(loc, self.dimensions[0]+10, size+3)
        Button.buttons.append(self)

    def draw(self, mouse_x, mouse_y):
        # draw something to refresh buffer?
        shader2Dcolor.uniform_float("color", (0, 0, 0, 0))
        batch_for_shader(shader2Dcolor, 'POINTS', {"pos": [(0,0), ]}).draw(shader2Dcolor)

        if is_in_rect(self, Vector((mouse_x, mouse_y))):
            shader2Dcolor.uniform_float("color", self.bg_color_selected)
        else:
            shader2Dcolor.uniform_float("color", self.bg_color)
        batch_for_shader(shader2Dcolor, 'TRI_STRIP', {"pos": self.get_verts()}).draw(shader2Dcolor)
        blf.size(self.font_id, self.font_size, 72)
        blf.position(self.font_id, self.point_lt.x + 5, self.point_rb.y + 4, 0)
        blf.color(self.font_id, *self.font_color)
        blf.draw(self.font_id, self.text)

    def click(self, args=None):
        return self.function(args)

view_layers = []

class Border(Rectangle):
    weight = 3

    def __init__(self, light_image, color):
        self.color = color
        self.light_image = light_image
        super().__init__(Vector((0, 0)), 100, 100)

    def draw(self):
        verts = self.get_verts()
        lleft = min(verts, key=lambda v: v[0])[0]
        lright = max(verts, key=lambda v: v[0])[0]

        bleft = self.light_image.panel.point_lt[0]
        bright = self.light_image.panel.point_rb[0]

        from mathutils import Euler
        rot_translate = Vector((self.weight, 0, 0))
        rot_translate.rotate(Euler((0,0,self.rot)))
        rot_translate_ort = Vector((-rot_translate.y, rot_translate.x))

                #       0   1
        # 0  lt.x, lt.y         0 2
        # 1  lt.x, rb.y         1 3
        # 2  rb.x, lt.y
        # 3  rb.x, rb.y

        left_verts = [
            verts[0],
            verts[1],
            [verts[0][0]+rot_translate.x, verts[0][1]+rot_translate.y],
            [verts[1][0]+rot_translate.x, verts[1][1]+rot_translate.y]
        ]

        right_verts = [
            [verts[2][0]-rot_translate.x, verts[2][1]-rot_translate.y],
            [verts[3][0]-rot_translate.x, verts[3][1]-rot_translate.y],
            verts[2],
            verts[3]
        ]

        top_verts = [
            verts[0],
            [verts[0][0]-rot_translate_ort.x, verts[0][1]-rot_translate_ort.y],
            verts[2],
            [verts[2][0]-rot_translate_ort.x, verts[2][1]-rot_translate_ort.y]
        ]

        bottom_verts = [
            [verts[1][0]+rot_translate_ort.x, verts[1][1]+rot_translate_ort.y],
            verts[1],
            [verts[3][0]+rot_translate_ort.x, verts[3][1]+rot_translate_ort.y],
            verts[3]
        ]

        border_shader2Dcolor.bind()
        bgl.glEnable(bgl.GL_BLEND)
        border_shader2Dcolor.uniform_float("color", self.color)
        border_shader2Dcolor.uniform_float("panel_point_lt", self.light_image.panel.point_lt)
        border_shader2Dcolor.uniform_float("panel_point_rb", self.light_image.panel.point_rb)
        if lleft < bleft:
            left_verts2 = deepcopy(left_verts)
            for v in left_verts2:
                v[0] += self.light_image.panel.width

            right_verts2 = deepcopy(right_verts)
            for v in right_verts2:
                v[0] += self.light_image.panel.width

            top_verts2 = deepcopy(top_verts)
            for v in top_verts2:
                v[0] += self.light_image.panel.width

            bottom_verts2 = deepcopy(bottom_verts)
            for v in bottom_verts2:
                v[0] += self.light_image.panel.width

            batch_for_shader(border_shader2Dcolor, 'TRI_STRIP', {"pos": left_verts2}).draw(border_shader2Dcolor)
            batch_for_shader(border_shader2Dcolor, 'TRI_STRIP', {"pos": right_verts2}).draw(border_shader2Dcolor)
            batch_for_shader(border_shader2Dcolor, 'TRI_STRIP', {"pos": top_verts2}).draw(border_shader2Dcolor)
            batch_for_shader(border_shader2Dcolor, 'TRI_STRIP', {"pos": bottom_verts2}).draw(border_shader2Dcolor)
        elif lright > bright:
            left_verts2 = deepcopy(left_verts)
            for v in left_verts2:
                v[0] -= self.light_image.panel.width

            right_verts2 = deepcopy(right_verts)
            for v in right_verts2:
                v[0] -= self.light_image.panel.width

            top_verts2 = deepcopy(top_verts)
            for v in top_verts2:
                v[0] -= self.light_image.panel.width

            bottom_verts2 = deepcopy(bottom_verts)
            for v in bottom_verts2:
                v[0] -= self.light_image.panel.width

            batch_for_shader(border_shader2Dcolor, 'TRI_STRIP', {"pos": left_verts2}).draw(border_shader2Dcolor)
            batch_for_shader(border_shader2Dcolor, 'TRI_STRIP', {"pos": right_verts2}).draw(border_shader2Dcolor)
            batch_for_shader(border_shader2Dcolor, 'TRI_STRIP', {"pos": top_verts2}).draw(border_shader2Dcolor)
            batch_for_shader(border_shader2Dcolor, 'TRI_STRIP', {"pos": bottom_verts2}).draw(border_shader2Dcolor)

        batch_for_shader(border_shader2Dcolor, 'TRI_STRIP', {"pos": left_verts}).draw(border_shader2Dcolor)
        batch_for_shader(border_shader2Dcolor, 'TRI_STRIP', {"pos": right_verts}).draw(border_shader2Dcolor)
        batch_for_shader(border_shader2Dcolor, 'TRI_STRIP', {"pos": top_verts}).draw(border_shader2Dcolor)
        batch_for_shader(border_shader2Dcolor, 'TRI_STRIP', {"pos": bottom_verts}).draw(border_shader2Dcolor)
        bgl.glDisable(bgl.GL_BLEND)

    def get_verts(self):
        self.point_lt = self.light_image.point_lt.copy()
        self.point_rb = self.light_image.point_rb.copy()

        self.point_lt.x -= self.weight
        self.point_lt.y += self.weight

        self.point_rb.x += self.weight
        self.point_rb.y -= self.weight

        self.rot = self.light_image.rot

        return super().get_verts()


class LightImage(Rectangle):
    selected_object = None
    lights = []
    @classmethod
    def find_idx(cls, lls_light_collection):
        for idx, l in enumerate(cls.lights):
            if l._collection == lls_light_collection:
                return idx
        return -1
    @classmethod
    def remove(cls, lls_light_collection):
        del cls.lights[cls.find_idx(lls_light_collection)]

    def delete(self):
        del LightImage.lights[LightImage.lights.index(self)]

    @classmethod
    def refresh(cls):
        props = bpy.context.scene.LLStudio

        cls.selected_object = None
        for l in cls.lights:
            try:
                if l.update_from_lls():
                    l.update_visual_location()
            except ReferenceError:
                l.delete()


    default_size = 100
    @classmethod
    def change_default_size(cls, value):
        cls.default_size = value
        for l in cls.lights:
            l.width = value * l._scale.y
            l.height = value * l._scale.z

    def panel_loc_to_area_px_lt(self):
        panel_px_loc = Vector((self.panel.width * self.panel_loc.x, -self.panel.height * (1-self.panel_loc.y)))
        return panel_px_loc + self.panel.point_lt - Vector((LightImage.default_size*self._scale.y/2, LightImage.default_size*self._scale.z/2))

    def _update_panel_loc(self):
        self.panel_loc.x = (self._lls_rot.x + pi) % (2*pi) / (2*pi)
        self.panel_loc.y = fmod(self._lls_rot.y + pi/2, pi) / (pi)

    def update_from_lls(self):
        if self._lls_mesh.select_get():
            LightImage.selected_object = self

        updated = False
        if self._lls_rot != self._lls_actuator.rotation_euler:
            updated |= True
            self._lls_rot = self._lls_actuator.rotation_euler.copy()
        if self.rot != self._lls_mesh.rotation_euler.x:
            updated |= True
            self.rot = self._lls_mesh.rotation_euler.x
        if self._scale != self._lls_mesh.scale:
            updated |= True
            self._scale = self._lls_mesh.scale.copy()
            self.width = LightImage.default_size * self._scale.y
            self.height = LightImage.default_size * self._scale.z

        if updated:
            self._update_panel_loc()

        if self._image_path != self._lls_mesh.active_material.node_tree.nodes["Light Texture"].image.filepath:
            updated |= True
            self.image = self._lls_mesh.active_material.node_tree.nodes["Light Texture"].image
            self._image_path = self._lls_mesh.active_material.node_tree.nodes["Light Texture"].image.filepath
        # this should run when image changes but sometimes Blender looses images... so it's run every time to be safe
        if self.image.gl_load():
            raise Exception


        return updated

    def update_lls(self):
        self._lls_actuator.rotation_euler = self._lls_rot
        self._lls_mesh.rotation_euler.x = self.rot

    def __init__(self, context, panel, lls_light_collection):
        self.panel = panel
        self.__panel_loc = Vector((.5, .5))

        # try:
        self._collection = lls_light_collection
        self._lls_mesh = [m for m in lls_light_collection.objects if m.name.startswith("LLS_LIGHT_MESH")][0]
        self._lls_actuator = self._lls_mesh.parent
        self._view_layer = find_view_layer(self._collection, context.view_layer.layer_collection)
        # except Exception:
        #     raise Exception

        self._image_path = ""
        self._lls_rot = None
        self._scale = None

        super().__init__(Vector((0,0)), LightImage.default_size, LightImage.default_size)
        self.update_from_lls()
        self.update_visual_location()

        LightImage.lights.append(self)

        self.default_border = Border(self, (.2, .35, .2, 1))
        self.mute_border = Border(self, (.7, 0, 0, 1))
        self.select_border = Border(self, (.2, .9, .2, 1))
        #self.select_border.weight = 2

    @property
    def mute(self):
        return self._view_layer.exclude

    @mute.setter
    def mute(self, value):
        self._view_layer.exclude = value

    @property
    def panel_loc(self):
        return self.__panel_loc

    @panel_loc.setter
    def panel_loc(self, pos):
        self.__panel_loc = pos
        self._lls_rot = Vector((
            (self.panel_loc.x -.5) * (2*pi),
            (self.panel_loc.y -.5) * (pi),
            self._lls_rot.z
        ))
        self.update_visual_location() # update self.loc

    def select(self):
        if self.mute:
            return
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = self._lls_mesh
        self._lls_mesh.select_set(True)

    def is_mouse_over(self, mouse_x, mouse_y):
        def rotate(x1, y1, offset):
            x1 -= offset.x
            y1 -= offset.y
            x2 = cos(-self.rot) * x1 - sin(-self.rot) * y1
            y2 = sin(-self.rot) * x1 + cos(-self.rot) * y1
            x2 += offset.x
            y2 += offset.y
            return [x2, y2]

        bleft = self.panel.point_lt[0]
        bright = self.panel.point_rb[0]

        if mouse_x > bright or mouse_x < bleft:
            return False

        tmouse_x, tmouse_y = rotate(mouse_x, mouse_y, self.loc)
        if (tmouse_y <= self.point_lt[1] and tmouse_y >= self.point_rb[1]) and\
            (tmouse_x <= self.point_rb[0] and tmouse_x >= self.point_lt[0]):
            return True

        tmouse_x, tmouse_y = rotate(bleft-(bright-mouse_x), mouse_y, self.loc)
        if (tmouse_y <= self.point_lt[1] and tmouse_y >= self.point_rb[1]) and\
            (tmouse_x <= self.point_rb[0] and tmouse_x >= self.point_lt[0]):
            return True

        tmouse_x, tmouse_y = rotate(bright+(mouse_x-bleft), mouse_y, self.loc)
        if (tmouse_y <= self.point_lt[1] and tmouse_y >= self.point_rb[1]) and\
            (tmouse_x <= self.point_rb[0] and tmouse_x >= self.point_lt[0]):
            return True

        return False

    def draw(self):
        try:
            select = self._lls_mesh.select_get()
        except ReferenceError:
            return

        # draw something to refresh buffer?
        shader2Dcolor.uniform_float("color", (0, 0, 0, 0))
        batch_for_shader(shader2Dcolor, 'POINTS', {"pos": [(0,0), ]}).draw(shader2Dcolor)

        bleft = self.panel.point_lt[0]
        bright = self.panel.point_rb[0]

        verts = self.get_verts()
        uv_coords = self.get_tex_coords()

        lleft = min(verts, key=lambda v: v[0])[0]
        lright = max(verts, key=lambda v: v[0])[0]

        if self.mute:
            self.mute_border.draw()
        elif select:
            self.select_border.draw()
        else:
            self.default_border.draw()

        lightIconShader.bind()
        bgl.glActiveTexture(bgl.GL_TEXTURE0)
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, self.image.bindcode)
        lightIconShader.uniform_int("image", 0)

        lightIconShader.uniform_float("panel_point_lt", self.panel.point_lt)
        lightIconShader.uniform_float("panel_point_rb", self.panel.point_rb)

        try:
            # material properties
            lls_node = self._lls_mesh.active_material.node_tree.nodes['Group']
            intensity = lls_node.inputs['Intensity'].default_value

            texture_switch = lls_node.inputs['Texture Switch'].default_value
            color_overlay = lls_node.inputs['Color Overlay'].default_value
            color_saturation = lls_node.inputs['Color Saturation'].default_value

            lightIconShader.uniform_float("intensity", intensity)
            lightIconShader.uniform_float("texture_switch", texture_switch)
            lightIconShader.uniform_float("color_overlay", color_overlay)
            lightIconShader.uniform_float("color_saturation", color_saturation)

            mask_bottom_to_top = lls_node.inputs['Mask - Bottom to Top'].default_value
            mask_diagonal_bottom_left = lls_node.inputs['Mask - Diagonal Bottom Left'].default_value
            mask_diagonal_bottom_right = lls_node.inputs['Mask - Diagonal Bottom Right'].default_value
            mask_diagonal_top_left = lls_node.inputs['Mask - Diagonal Top Left'].default_value
            mask_diagonal_top_right = lls_node.inputs['Mask - Diagonal Top Right'].default_value
            mask_gradient_amount = lls_node.inputs['Mask - Gradient Amount'].default_value
            mask_gradient_switch = lls_node.inputs['Mask - Gradient Switch'].default_value
            mask_gradient_type = lls_node.inputs['Mask - Gradient Type'].default_value
            mask_left_to_right = lls_node.inputs['Mask - Left to Right'].default_value
            mask_right_to_left = lls_node.inputs['Mask - Right to Left'].default_value
            mask_ring_inner_radius = lls_node.inputs['Mask - Ring Inner Radius'].default_value
            mask_ring_outer_radius = lls_node.inputs['Mask - Ring Outer Radius'].default_value
            mask_ring_switch = lls_node.inputs['Mask - Ring Switch'].default_value
            mask_top_to_bottom = lls_node.inputs['Mask - Top to Bottom'].default_value

            lightIconShader.uniform_float("mask_bottom_to_top", mask_bottom_to_top)
            lightIconShader.uniform_float("mask_diagonal_bottom_left", mask_diagonal_bottom_left)
            lightIconShader.uniform_float("mask_diagonal_bottom_right", mask_diagonal_bottom_right)
            lightIconShader.uniform_float("mask_diagonal_top_left", mask_diagonal_top_left)
            lightIconShader.uniform_float("mask_diagonal_top_right", mask_diagonal_top_right)
            lightIconShader.uniform_float("mask_gradient_amount", mask_gradient_amount)
            lightIconShader.uniform_float("mask_gradient_switch", mask_gradient_switch)
            lightIconShader.uniform_float("mask_gradient_type", mask_gradient_type)
            lightIconShader.uniform_float("mask_left_to_right", mask_left_to_right)
            lightIconShader.uniform_float("mask_right_to_left", mask_right_to_left)
            lightIconShader.uniform_float("mask_ring_inner_radius", mask_ring_inner_radius)
            lightIconShader.uniform_float("mask_ring_outer_radius", mask_ring_outer_radius)
            lightIconShader.uniform_float("mask_ring_switch", mask_ring_switch)
            lightIconShader.uniform_float("mask_top_to_bottom", mask_top_to_bottom)
        except:
            pass
        bgl.glEnable(bgl.GL_BLEND)

        if lleft < bleft:
            verts2 = deepcopy(verts)
            for v in verts2:
                v[0] += self.panel.width

            batch_for_shader(
                lightIconShader, 'TRI_STRIP',
                {
                    "pos": verts,
                    "texCoord": uv_coords,
                }
            ).draw(lightIconShader)

            batch_for_shader(
                lightIconShader, 'TRI_STRIP',
                {
                    "pos": verts2,
                    "texCoord": uv_coords,
                }
            ).draw(lightIconShader)
        elif lright > bright:
            verts2 = deepcopy(verts)
            for v in verts2:
                v[0] -= self.panel.width

            batch_for_shader(
                lightIconShader, 'TRI_STRIP',
                {
                    "pos": verts,
                    "texCoord": uv_coords,
                }
            ).draw(lightIconShader)

            batch_for_shader(
                lightIconShader, 'TRI_STRIP',
                {
                    "pos": verts2,
                    "texCoord": uv_coords,
                }
            ).draw(lightIconShader)
        else:
            batch_for_shader(
                lightIconShader, 'TRI_STRIP',
                {
                    "pos": verts,
                    "texCoord": self.get_tex_coords(),
                }
            ).draw(lightIconShader)
        bgl.glDisable(bgl.GL_BLEND)

    def update_visual_location(self):
        self.loc = self.panel_loc_to_area_px_lt() + Vector((self.width/2, self.height/2))

    def move(self, loc_diff):
        super().move(loc_diff)

        self.panel_loc = Vector((
            (self.loc.x-self.panel.loc.x) / self.panel.width +.5,
            clamp(0.0001, (self.loc.y-self.panel.loc.y) / self.panel.height +.5, 0.9999),
        ))

        self.update_lls()

def is_in_rect(rect, loc):
    return (loc.x >= rect.point_lt.x and loc.x <= rect.point_rb.x) and (loc.y >= rect.point_rb.y and loc.y <= rect.point_lt.y)

def clamp(minimum, x, maximum):
    return max(minimum, min(x, maximum))

class ClickManager:
    def __init__(self):
        self.times = [0, 0, 0]
        self.objects = [None, None, None]

    def click(self, object):
        self.times.append(time.time())
        self.objects.append(object)
        if len(self.times) > 3:
            del self.times[0]
            del self.objects[0]

        if self.objects[0] == self.objects[1] == self.objects[2]:
            if self.times[2] - self.times[0] <= .5:
                return "TRIPLE"
        if self.objects[1] == self.objects[2]:
            if self.times[2] - self.times[1] <= .5:
                return "DOUBLE"

class MouseWidget:
    mouse_x: bpy.props.IntProperty()
    mouse_y: bpy.props.IntProperty()

    def __init__(self):
        self._start_position = None
        self._end_position = Vector((0, 0))
        self._reference_end_position = Vector((0, 0))
        self._base_rotation = 0
        self.handler = None

        self.draw_guide = True

        self.allow_xy_keys = False
        self.x_key = False
        self.y_key = False
        self.z_key = False

        self.continous = False

        self.allow_precision_mode = False
        self.precision_mode = False
        self.precision_offset = Vector((0,0))
        self.precision_factor = 0.1

        self.z_start_position = Vector((0,0))
        self.z_end_position = Vector((0,0))

    def invoke(self, context, event):
        mouse_x = event.mouse_x - context.area.x
        mouse_y = event.mouse_y - context.area.y

        self._start_position = Vector((self.mouse_x, self.mouse_y))
        self._end_position = Vector((mouse_x, mouse_y))
        self._reference_end_position = self._end_position
        vec = self._end_position - self._start_position
        self._base_rotation = atan2(vec.y, vec.x)

        self.handler = bpy.types.SpaceView3D.draw_handler_add(self._draw, (context, event,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)

    def _cancel(self, context, event): pass
    def _finish(self, context, event): pass

    def modal(self, context, event):
        # print(event.type, event.value)
        if not context.area:
            self._unregister_handler()
            self._cancel(context, event)
            return {"CANCELLED"}

        if event.type in {"ESC", "RIGHTMOUSE"}:
            self._unregister_handler()
            self._cancel(context, event)
            return {'CANCELLED'}

        if event.type == "RET" or (not self.continous and event.type == "LEFTMOUSE"):
            self._unregister_handler()
            self._finish(context, event)
            return {'FINISHED'}

        if self.continous and event.value == "RELEASE" and event.type == "LEFTMOUSE":
            self._unregister_handler()
            self._finish(context, event)
            return {'FINISHED'}

        self.mouse_x = event.mouse_x - context.area.x
        self.mouse_y = event.mouse_y - context.area.y
        self._end_position = Vector((self.mouse_x, self.mouse_y))

        if self.allow_xy_keys:
            if event.value == "PRESS":
                if event.type == "X":
                    self.x_key = not self.x_key
                    self.y_key = False
                    self.z_key = False
                if event.type == "Y":
                    self.y_key = not self.y_key
                    self.x_key = False
                    self.z_key = False
                if event.type == "Z":
                    self.z_key = not self.z_key
                    self.x_key = False
                    self.y_key = False

        if self.allow_precision_mode and event.value == "PRESS" and event.type == "LEFT_SHIFT":
            self.precision_mode = True
            self._precision_mode_mid_stop = self._end_position.copy()
        elif self.allow_precision_mode and event.value == "RELEASE" and event.type == "LEFT_SHIFT" and self.precision_mode: #last condition in case when operator invoked with shift already pressed
            self.precision_mode = False
            self.precision_offset += self._end_position - self._precision_mode_mid_stop

        return self._modal(context, event)

    def __del__(self):
        self._unregister_handler()

    def _unregister_handler(self):
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self.handler, 'WINDOW')
        except (ValueError, AttributeError):
            pass

    def length(self):
        return (self._start_position - self._reference_end_position - self.delta_vector()).length

    def delta_vector(self):
        precision_factor_inv = 1 - self.precision_factor
        if self.precision_mode:
            return self._precision_mode_mid_stop - self._reference_end_position - self.precision_offset * precision_factor_inv + (self._end_position - self._precision_mode_mid_stop) * self.precision_factor
        return self._end_position - self._reference_end_position - self.precision_offset * precision_factor_inv

    def delta_length_factor(self):
        return self.length() / ((self._start_position - self._reference_end_position).length)

    def angle(self):
        vec = self._reference_end_position - self._start_position + self.delta_vector() + self.precision_offset * (1 - self.precision_factor)
        return atan2(vec.y, vec.x) - self._base_rotation

    def _draw(self, context, event):
        # first draw to reset buffer
        shader2Dcolor.uniform_float("color", (.5, .5, .5, .5))
        batch_for_shader(shader2Dcolor, 'LINES', {"pos": ((0,0), (0,0))}).draw(shader2Dcolor)

        if self.draw_guide:
            shader2Dcolor.uniform_float("color", (.5, .5, .5, .5))
            batch_for_shader(shader2Dcolor, 'LINES', {"pos": ((self._start_position[:]), (self._end_position[:]))}).draw(shader2Dcolor)

        if self.allow_xy_keys:
            if self.x_key:
                shader2Dcolor.uniform_float("color", (1, 0, 0, .5))
                batch_for_shader(shader2Dcolor, 'LINES', {"pos": ((0, self._start_position.y), (context.area.width, self._start_position.y))}).draw(shader2Dcolor)
            elif self.y_key:
                shader2Dcolor.uniform_float("color", (0, 1, 0, .5))
                batch_for_shader(shader2Dcolor, 'LINES', {"pos": ((self._start_position.x, 0), (self._start_position.x, context.area.height))}).draw(shader2Dcolor)
            elif self.z_key:
                shader2Dcolor.uniform_float("color", (0, 0, 1, .5))
                batch_for_shader(shader2Dcolor, 'LINES', {"pos": (self.z_start_position, self.z_end_position)}).draw(shader2Dcolor)