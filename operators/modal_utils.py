import gpu, blf
from gpu_extras.batch import batch_for_shader
from mathutils import *
from math import pi, fmod, radians, sin, cos, atan2
from .. common import *
from . import *
import time
from copy import deepcopy

shader2Dcolor = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
shader2Dcolor.bind()

# ##################################
vert_out = gpu.types.GPUStageInterfaceInfo("my_interface")
vert_out.smooth('VEC2', "texCoord_interp")

shader_info = gpu.types.GPUShaderCreateInfo()
shader_info.push_constant('MAT4', "ModelViewProjectionMatrix")
shader_info.push_constant('BOOL', 'advanced')
shader_info.sampler(0, 'FLOAT_2D', "image")

shader_info.typedef_source(
"""
    struct Data {
        float4 color_overlay;
        float2 panel_point_lt;
        float2 panel_point_rb;
        float intensity;
        float exposure;
        float texture_switch;
        float color_saturation;
        float mask_bottom_to_top;
        float mask_diagonal_bottom_left;
        float mask_diagonal_bottom_right;
        float mask_diagonal_top_left;
        float mask_diagonal_top_right;
        float mask_gradient_amount;
        float mask_gradient_switch;
        float mask_gradient_type;
        float mask_left_to_right;
        float mask_right_to_left;
        float mask_ring_inner_radius;
        float mask_ring_outer_radius;
        float mask_ring_switch;
        float mask_top_to_bottom;
        float2 _pad;
    };
    BLI_STATIC_ASSERT_ALIGN(Data, 16)
"""
)

import ctypes
class _UBO_struct(ctypes.Structure):
    _pack_ = 16
    _fields_ = [
        ("color_overlay", ctypes.c_float*4), # 16 B
        ("panel_point_lt", ctypes.c_float*2), # 8 B
        ("panel_point_rb", ctypes.c_float*2), # 8 B
        ("intensity", ctypes.c_float),
        ("exposure", ctypes.c_float),
        ("texture_switch", ctypes.c_float),
        ("color_saturation", ctypes.c_float),
        ("mask_bottom_to_top", ctypes.c_float),
        ("mask_diagonal_bottom_left", ctypes.c_float),
        ("mask_diagonal_bottom_right", ctypes.c_float),
        ("mask_diagonal_top_left", ctypes.c_float),
        ("mask_diagonal_top_right", ctypes.c_float),
        ("mask_gradient_amount", ctypes.c_float),
        ("mask_gradient_switch", ctypes.c_float),
        ("mask_gradient_type", ctypes.c_float),
        ("mask_left_to_right", ctypes.c_float),
        ("mask_right_to_left", ctypes.c_float),
        ("mask_ring_inner_radius", ctypes.c_float),
        ("mask_ring_outer_radius", ctypes.c_float),
        ("mask_ring_switch", ctypes.c_float),
        ("mask_top_to_bottom", ctypes.c_float),
        ("_pad", ctypes.c_float*2),
    ]

UBO_data = _UBO_struct()

shader_info.vertex_in(0, 'VEC2', "pos")
shader_info.vertex_in(1, 'VEC2', "texCoord")
shader_info.uniform_buf(0, 'Data', "g_data")
shader_info.vertex_out(vert_out)
shader_info.fragment_out(0, 'VEC4', "fragColor")
shader_info.fragment_out(1, 'VEC4', "trash")

shader_info.vertex_source(
    """
    void main()
    {
        gl_Position = ModelViewProjectionMatrix * vec4(pos.xy, 0.0f, 1.0f);
        gl_Position.z = 1.0;
        texCoord_interp = texCoord;
    }
    """
)

shader_info.fragment_source(
    """
    void main()
    {
        // Trash output - sum all uniforms to prevent compiler from skipping currently unused ones
        trash = vec4(g_data.color_overlay.x+g_data.exposure+g_data.panel_point_lt.x+g_data.panel_point_rb.x+g_data.mask_bottom_to_top+g_data.mask_diagonal_bottom_left+g_data.mask_diagonal_bottom_right+g_data.mask_diagonal_top_left+g_data.mask_diagonal_top_right+g_data.mask_gradient_amount+g_data.mask_gradient_switch+g_data.mask_gradient_type+g_data.mask_left_to_right+g_data.mask_right_to_left+g_data.mask_ring_inner_radius+g_data.mask_ring_outer_radius+g_data.mask_ring_switch+g_data.mask_top_to_bottom+int(advanced));
    
        if(advanced){
            // Texture Switch + Intensity
            // log(1+g_data.intensity) so the images won't get overexposed too fast when high intensity values used
            
            // set non-zero min color value to sort of simulate overexposure visible on real light object in viewport
            vec4 tex = texture(image, texCoord_interp);
            tex.r = max(0.05, tex.r);
            tex.g = max(0.05, tex.g);
            tex.b = max(0.05, tex.b);
            
            fragColor = mix(vec4(1.0f), tex, g_data.texture_switch) * log(1+g_data.intensity) * pow((g_data.exposure+10)/11, 2);

            // Color Overlay
            float gray = clamp(float(dot(fragColor.rgb, vec3(0.299, 0.587, 0.114))), 0.0f, 1.0f);
            vec4 colored = g_data.color_overlay * gray;

            // Color Saturation
            fragColor = mix(fragColor, colored, g_data.color_saturation);
            fragColor.a = gray;
            fragColor.rgb *= fragColor.a;

            // MASKS //

            // Vertical gradient + mask_gradient_amount
            float vg = sqrt(texCoord_interp.y);
            vg = (texCoord_interp.y <= g_data.mask_gradient_amount+.05f) ? mix(0.0f, vg, (texCoord_interp.y-g_data.mask_gradient_amount)/.05f) : vg;
            vg = texCoord_interp.y >= g_data.mask_gradient_amount ? vg : 0;

            // Spherical gradient + g_data.mask_gradient_amount
            float d = distance(texCoord_interp.xy, vec2(0.5f, 0.5f));
            float m = (1.0f-g_data.mask_gradient_amount)*.5f;
            float sg = 1-pow(d*2, 2.f);
            sg = (d >= m-.05f) ? mix(0.0f, sg, (m-d)/.05f) : sg;
            sg = (d <= m) ? sg : 0;

            // Gradient Type
            float grad = mix(sg, vg, g_data.mask_gradient_type);

            // Gradient Switch
            fragColor.a = mix(fragColor.a, grad*fragColor.a, g_data.mask_gradient_switch);

            // Gradient Ring Switch
            float ring = d < (1-g_data.mask_ring_outer_radius)*.575f ? 1 : 0;
            ring = d < (1-g_data.mask_ring_inner_radius)*.55f ? 0 : ring;
            fragColor.a = mix(fragColor.a, fragColor.a*ring, g_data.mask_ring_switch);

            // Top-Bottom
            fragColor.a = texCoord_interp.y < (1-g_data.mask_top_to_bottom) ? fragColor.a : 0;

            // Bottom-Top
            fragColor.a = texCoord_interp.y > g_data.mask_bottom_to_top ? fragColor.a : 0;

            // Left-Right
            fragColor.a = texCoord_interp.x > g_data.mask_left_to_right ? fragColor.a : 0;

            // Right-Left
            fragColor.a = texCoord_interp.x < (1-g_data.mask_right_to_left) ? fragColor.a : 0;

            // Diagonal Top-Right
            fragColor.a = 1-(texCoord_interp.x+texCoord_interp.y)/2 > g_data.mask_diagonal_top_right ? fragColor.a : 0;

            // Diagonal Top-Left
            fragColor.a = 1-(1-texCoord_interp.x+texCoord_interp.y)/2 > g_data.mask_diagonal_top_left ? fragColor.a : 0;

            // Diagonal Bottom-Right
            fragColor.a = (1-texCoord_interp.x+texCoord_interp.y)/2 > g_data.mask_diagonal_bottom_right ? fragColor.a : 0;

            // Diagonal Bottom-Left
            fragColor.a = (texCoord_interp.x+texCoord_interp.y)/2 > g_data.mask_diagonal_bottom_left ? fragColor.a : 0;
        }else{
            fragColor = mix(vec4(1.0f), g_data.color_overlay, g_data.color_saturation) * log(1+g_data.intensity);
        }
    
        // Panel bound clipping
        if((gl_FragCoord.x < g_data.panel_point_lt.x || gl_FragCoord.x > g_data.panel_point_rb.x)
         || (gl_FragCoord.y < g_data.panel_point_rb.y || gl_FragCoord.y > g_data.panel_point_lt.y))
            discard;
    
    }
    """
)
lightIconShader = gpu.shader.create_from_info(shader_info)
UBO = gpu.types.GPUUniformBuf(
    gpu.types.Buffer("UBYTE", ctypes.sizeof(UBO_data), UBO_data)
)
lightIconShader.uniform_block("g_data", UBO)
del vert_out
del shader_info

# #####################################################

border_vertex_shader= '''
    void main()
    {
        gl_Position = ModelViewProjectionMatrix * vec4(pos, 0.0, 1.0);
    }
'''
border_fragment_shader= '''
    void main()
    {
        fragColor = color;

        if((gl_FragCoord.x < panel_point_lt.x || gl_FragCoord.x > panel_point_rb.x)
         || (gl_FragCoord.y < panel_point_rb.y || gl_FragCoord.y > panel_point_lt.y))
            discard;
    }
'''

vert_out = gpu.types.GPUStageInterfaceInfo("my_interface")
vert_out.smooth('VEC2', "texCoord_interp")

shader_info = gpu.types.GPUShaderCreateInfo()
shader_info.push_constant('MAT4', "ModelViewProjectionMatrix")
shader_info.push_constant('VEC4', "color")
shader_info.push_constant('VEC2', "panel_point_lt")
shader_info.push_constant('VEC2', "panel_point_rb")
shader_info.vertex_in(0, 'VEC2', 'pos')
shader_info.vertex_source(border_vertex_shader)

shader_info.fragment_out(0, 'VEC4', "fragColor")
shader_info.fragment_source(border_fragment_shader)

border_shader2Dcolor = gpu.shader.create_from_info(shader_info)
del vert_out
del shader_info


from . import AREA_DEFAULT_SIZE

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
            self.point_rb.y - self.button_exit.dimensions[1]/2 - 13,
        ))

        self.button_fast_3d_edit.loc = Vector((
            self.point_lt.x + self.button_send_to_bottom.dimensions[0] + self.button_fast_3d_edit.dimensions[0]/2 + 23,
            self.point_rb.y - self.button_exit.dimensions[1]/2 - 13,
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

        super().__init__(loc, self.dimensions[0]+10, size+10)
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
        blf.position(self.font_id, self.point_lt.x + 5, self.point_rb.y + 7, 0)
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
        gpu.state.blend_set("ALPHA")
        border_shader2Dcolor.uniform_float("color", self.color)
        border_shader2Dcolor.uniform_float("panel_point_lt", self.light_image.panel.point_lt)
        border_shader2Dcolor.uniform_float("panel_point_rb", self.light_image.panel.point_rb)
        print(self.color)
        print(self.light_image.panel.point_lt)
        print(self.light_image.panel.point_rb)
        
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

        print(left_verts)
        batch_for_shader(border_shader2Dcolor, 'TRI_STRIP', {"pos": left_verts}).draw(border_shader2Dcolor)
        batch_for_shader(border_shader2Dcolor, 'TRI_STRIP', {"pos": right_verts}).draw(border_shader2Dcolor)
        batch_for_shader(border_shader2Dcolor, 'TRI_STRIP', {"pos": top_verts}).draw(border_shader2Dcolor)
        batch_for_shader(border_shader2Dcolor, 'TRI_STRIP', {"pos": bottom_verts}).draw(border_shader2Dcolor)
        gpu.state.blend_set("NONE")

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
            l.width = value * l._scale.x
            l.height = value * l._scale.z

    def panel_loc_to_area_px_lt(self):
        panel_px_loc = Vector((self.panel.width * self.panel_loc.x, -self.panel.height * (1-self.panel_loc.y)))
        return panel_px_loc + self.panel.point_lt - Vector((LightImage.default_size*self._scale.x/2, LightImage.default_size*self._scale.z/2))

    def _update_panel_loc(self):
        self.panel_loc.x = (self._lls_rot.x + pi) % (2*pi) / (2*pi)
        self.panel_loc.y = fmod(self._lls_rot.y + pi/2, pi) / (pi)

    def update_from_lls(self):
        if not self._lls_object:
            return False
        
        if self._lls_object.select_get():
            LightImage.selected_object = self

        updated = False
        if self._lls_rot != self._lls_actuator.rotation_euler:
            updated |= True
            self._lls_rot = self._lls_actuator.rotation_euler.copy()
        if self.rot != self._lls_handle.rotation_euler.y:
            updated |= True
            self.rot = self._lls_handle.rotation_euler.y
        if self._scale != self._lls_handle.scale:
            updated |= True
            self._scale = self._lls_handle.scale.copy()
            self.width = LightImage.default_size * self._scale.x
            self.height = LightImage.default_size * self._scale.z
            self._lls_basic_collection.objects[0].data.LLStudio.intensity = self._lls_basic_collection.objects[0].data.LLStudio.intensity

        if updated:
            self._update_panel_loc()

        if self._lls_object.type == 'MESH':
            if self._image_path != self._lls_object.active_material.node_tree.nodes["Light Texture"].image.filepath:
                updated |= True
                self.image = self._lls_object.active_material.node_tree.nodes["Light Texture"].image
                self.gpu_texture = gpu.texture.from_image(self.image)
                self._image_path = self._lls_object.active_material.node_tree.nodes["Light Texture"].image.filepath

        return updated

    def update_lls(self):
        self._lls_actuator.rotation_euler = self._lls_rot
        self._lls_handle.rotation_euler.y = self.rot

    @property
    def _lls_object(self):
        type = self._lls_handle.LLStudio.type
        try:
            if type == 'ADVANCED':
                return [ob for ob in self._lls_handle.children if ob.name.startswith("LLS_LIGHT_MESH")][0]
            elif type == 'BASIC':
                return [ob for ob in self._lls_handle.children if ob.name.startswith("LLS_LIGHT_AREA")][0]
        except:
            # override = {'selected_objects': [self._lls_handle,]}
            # bpy.ops.scene.delete_leomoon_studio_light(override, confirm=False)
            raise Exception("Malformed light")
        return None

    def __init__(self, context, panel, lls_light_collection):
        self.panel = panel
        self.__panel_loc = Vector((.5, .5))

        self._collection = lls_light_collection
        self._lls_handle = [m for m in lls_light_collection.objects if m.name.startswith("LLS_LIGHT_HANDLE")][0]
        self._lls_actuator = self._lls_object.parent.parent
        self._view_layer = find_view_layer(self._collection, context.view_layer.layer_collection)

        self._lls_basic_collection = [m for m in lls_light_collection.children if m.name.startswith("LLS_Basic")][0]
        self._lls_advanced_collection = [m for m in lls_light_collection.children if m.name.startswith("LLS_Advanced")][0]
        self._basic_view_layer = find_view_layer(self._lls_basic_collection, context.view_layer.layer_collection)
        self._advanced_view_layer = find_view_layer(self._lls_advanced_collection, context.view_layer.layer_collection)


        self.image = self._lls_advanced_collection.objects[0].active_material.node_tree.nodes["Light Texture"].image
        self.gpu_texture = gpu.texture.from_image(self.image)
        self._image_path = self._lls_advanced_collection.objects[0].active_material.node_tree.nodes["Light Texture"].image.filepath
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
        self.active_border = Border(self, (.1, .45, .1, 1))

    @property
    def mute(self):
        return self._view_layer.exclude

    @mute.setter
    def mute(self, exclude):
        self._view_layer.exclude = exclude
        if not exclude:
            self._lls_handle.LLStudio.type = self._lls_handle.LLStudio.type

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
        # if self._lls_object.name in bpy.context.view_layer.objects:
        self._lls_handle.LLStudio.type = self._lls_handle.LLStudio.type
        bpy.context.view_layer.objects.active = self._lls_object
        self._lls_object.select_set(True)

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
            select = self._lls_object.select_get()
            # select = self._lls_object == bpy.context.active_object and self._lls_object.select_get()
            active_select = self._lls_object == bpy.context.active_object
        except ReferenceError:
            return
        except AttributeError:
            select = False

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
        elif select and active_select:
            self.select_border.draw()
        elif active_select:
            self.active_border.draw()
        else:
            self.default_border.draw()

        # lightIconShader.bind()
        UBO_data.panel_point_lt = (ctypes.c_float * len(self.panel.point_lt))(*self.panel.point_lt)
        UBO_data.panel_point_rb = (ctypes.c_float * len(self.panel.point_rb))(*self.panel.point_rb)
        
        if self._lls_handle.LLStudio.type == 'ADVANCED':
            lightIconShader.uniform_bool("advanced", [True,])
            lightIconShader.uniform_sampler("image", self.gpu_texture)

            try:
                # material properties
                lls_node = self._lls_object.active_material.node_tree.nodes['Group']
                intensity = lls_node.inputs['Intensity'].default_value
                exposure = lls_node.inputs['Exposure'].default_value

                texture_switch = lls_node.inputs['Texture Switch'].default_value
                color_overlay = lls_node.inputs['Color Overlay'].default_value
                color_saturation = lls_node.inputs['Color Saturation'].default_value

                UBO_data.intensity = intensity
                UBO_data.texture_switch = texture_switch
                UBO_data.color_overlay = (ctypes.c_float * len(color_overlay))(*color_overlay)
                UBO_data.color_saturation = color_saturation
                UBO_data.exposure = exposure

                UBO_data.color_saturation = self._lls_object.data.LLStudio.color_saturation
                v = Vector((self._lls_object.data.LLStudio.color[:]+(1,)))
                UBO_data.color_overlay = (ctypes.c_float * len(v))(*v)

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
                
                UBO_data.mask_bottom_to_top = mask_bottom_to_top
                UBO_data.mask_diagonal_bottom_left = mask_diagonal_bottom_left
                UBO_data.mask_diagonal_bottom_right = mask_diagonal_bottom_right
                UBO_data.mask_diagonal_top_left = mask_diagonal_top_left
                UBO_data.mask_diagonal_top_right = mask_diagonal_top_right
                UBO_data.mask_gradient_amount = mask_gradient_amount
                UBO_data.mask_gradient_switch = mask_gradient_switch
                UBO_data.mask_gradient_type = mask_gradient_type
                UBO_data.mask_left_to_right = mask_left_to_right
                UBO_data.mask_right_to_left = mask_right_to_left
                UBO_data.mask_ring_inner_radius = mask_ring_inner_radius
                UBO_data.mask_ring_outer_radius = mask_ring_outer_radius
                UBO_data.mask_ring_switch = mask_ring_switch
                UBO_data.mask_top_to_bottom = mask_top_to_bottom
            except:
                pass
        else:
            lightIconShader.uniform_bool("advanced", [False,])

            UBO_data.intensity = self._lls_object.data.LLStudio.intensity
            UBO_data.color_saturation = self._lls_object.data.LLStudio.color_saturation
            v = Vector((self._lls_object.data.LLStudio.color[:]+(1,)))
            UBO_data.color_overlay = (ctypes.c_float * len(v))(*v)


        
        gpu.state.blend_set("ALPHA")
        UBO = gpu.types.GPUUniformBuf(
            gpu.types.Buffer("UBYTE", ctypes.sizeof(UBO_data), UBO_data)
        )
        lightIconShader.uniform_block("g_data", UBO)
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
        gpu.state.blend_set("NONE")

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
    mouse_x: bpy.props.FloatProperty()
    mouse_y: bpy.props.FloatProperty()

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