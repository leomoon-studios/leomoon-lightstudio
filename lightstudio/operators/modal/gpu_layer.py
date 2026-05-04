"""GPU shaders + draw primitives for the 2D Control Panel modal.

Two custom shaders are built lazily on first use (no GPU context
required at import time):

* ``light_icon`` — textured + masked light thumbnail with panel-bound
  clipping. Uses a ``Data`` UBO whose layout matches
  :data:`lightstudio.core.light_io._GROUP_INPUT_KEYS`.
* ``border`` — coloured border around a light icon, also panel-clipped.

Plus four ``Rectangle``-derived primitives:

* :class:`Button` — labelled clickable rectangle (uses ``blf``).
* :class:`Panel` — full-screen control surface; constructs the three
  built-in buttons (X / Send to Bottom / Light Brush).
* :class:`Border` — coloured outline rendered around a :class:`LightImage`.
* :class:`LightImage` — bpy-coupled light thumbnail; holds a reference
  to the LLS_Light collection and reflects its rotation/scale in the
  panel.

Module-level state:

* :data:`view_layers` — list reused by the modal operator to remember
  per-profile view-layer state across draw calls (step 15c).
* :data:`UBO_data` — the ctypes struct mirroring the GLSL ``Data`` block.
"""

from __future__ import annotations

import contextlib
import ctypes
from copy import deepcopy
from math import asin, atan2, cos, fmod, pi, sin, sqrt

import blf
import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Euler, Vector

from ...core.scene_utils import find_view_layer
from ...core.widgets import Rectangle, clamp, is_in_rect

# ---------------------------------------------------------------------------
# UBO struct — 21 advanced shader inputs + panel clip rect + colour
# ---------------------------------------------------------------------------


class _UBO_struct(ctypes.Structure):
    _pack_ = 16
    _fields_ = [
        ("color_overlay", ctypes.c_float * 4),
        ("panel_point_lt", ctypes.c_float * 2),
        ("panel_point_rb", ctypes.c_float * 2),
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
        ("_pad", ctypes.c_float * 2),
    ]


UBO_data = _UBO_struct()


# ---------------------------------------------------------------------------
# Shader sources
# ---------------------------------------------------------------------------

_LIGHT_ICON_TYPEDEF = """
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
"""

_LIGHT_ICON_VERT = """
void main()
{
    gl_Position = ModelViewProjectionMatrix * vec4(pos.xy, 0.0f, 1.0f);
    gl_Position.z = 1.0;
    texCoord_interp = texCoord;
}
"""

_LIGHT_ICON_FRAG = """
void main()
{
    if(advanced){
        vec4 tex = texture(image, texCoord_interp);
        tex.r = max(0.05, tex.r);
        tex.g = max(0.05, tex.g);
        tex.b = max(0.05, tex.b);

        fragColor = mix(vec4(1.0f), tex, g_data.texture_switch)
            * log(1+g_data.intensity)
            * pow((g_data.exposure+10)/11, 2);

        float gray = clamp(float(dot(fragColor.rgb, vec3(0.299, 0.587, 0.114))), 0.0f, 1.0f);
        vec4 colored = g_data.color_overlay * gray;
        fragColor = mix(fragColor, colored, g_data.color_saturation);
        fragColor.a = gray;
        fragColor.rgb *= fragColor.a;

        // MASKS
        float vg = sqrt(texCoord_interp.y);
        vg = (texCoord_interp.y <= g_data.mask_gradient_amount+.05f)
            ? mix(0.0f, vg, (texCoord_interp.y-g_data.mask_gradient_amount)/.05f) : vg;
        vg = texCoord_interp.y >= g_data.mask_gradient_amount ? vg : 0;

        float d = distance(texCoord_interp.xy, vec2(0.5f, 0.5f));
        float m = (1.0f-g_data.mask_gradient_amount)*.5f;
        float sg = 1-pow(d*2, 2.f);
        sg = (d >= m-.05f) ? mix(0.0f, sg, (m-d)/.05f) : sg;
        sg = (d <= m) ? sg : 0;

        float grad = mix(sg, vg, g_data.mask_gradient_type);
        fragColor.a = mix(fragColor.a, grad*fragColor.a, g_data.mask_gradient_switch);

        float ring = d < (1-g_data.mask_ring_outer_radius)*.575f ? 1 : 0;
        ring = d < (1-g_data.mask_ring_inner_radius)*.55f ? 0 : ring;
        fragColor.a = mix(fragColor.a, fragColor.a*ring, g_data.mask_ring_switch);

        fragColor.a = texCoord_interp.y < (1-g_data.mask_top_to_bottom) ? fragColor.a : 0;
        fragColor.a = texCoord_interp.y > g_data.mask_bottom_to_top ? fragColor.a : 0;
        fragColor.a = texCoord_interp.x > g_data.mask_left_to_right ? fragColor.a : 0;
        fragColor.a = texCoord_interp.x < (1-g_data.mask_right_to_left) ? fragColor.a : 0;
        fragColor.a = 1-(texCoord_interp.x+texCoord_interp.y)/2 > g_data.mask_diagonal_top_right ? fragColor.a : 0;
        fragColor.a = 1-(1-texCoord_interp.x+texCoord_interp.y)/2 > g_data.mask_diagonal_top_left ? fragColor.a : 0;
        fragColor.a = (1-texCoord_interp.x+texCoord_interp.y)/2 > g_data.mask_diagonal_bottom_right ? fragColor.a : 0;
        fragColor.a = (texCoord_interp.x+texCoord_interp.y)/2 > g_data.mask_diagonal_bottom_left ? fragColor.a : 0;
    } else {
        fragColor = mix(vec4(1.0f), g_data.color_overlay, g_data.color_saturation)
            * log(1+g_data.intensity);
    }

    if((gl_FragCoord.x < g_data.panel_point_lt.x || gl_FragCoord.x > g_data.panel_point_rb.x)
     || (gl_FragCoord.y < g_data.panel_point_rb.y || gl_FragCoord.y > g_data.panel_point_lt.y))
        discard;
}
"""

_BORDER_VERT = """
void main()
{
    gl_Position = ModelViewProjectionMatrix * vec4(pos, 0.0, 1.0);
}
"""

_BORDER_FRAG = """
void main()
{
    fragColor = color;
    if((gl_FragCoord.x < panel_point_lt.x || gl_FragCoord.x > panel_point_rb.x)
     || (gl_FragCoord.y < panel_point_rb.y || gl_FragCoord.y > panel_point_lt.y))
        discard;
}
"""


# ---------------------------------------------------------------------------
# Shader builders (lazy)
# ---------------------------------------------------------------------------

_SHADERS: dict = {}


def _build_light_icon_shader():
    vert_out = gpu.types.GPUStageInterfaceInfo("lls_iface")
    vert_out.smooth("VEC2", "texCoord_interp")
    info = gpu.types.GPUShaderCreateInfo()
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.push_constant("BOOL", "advanced")
    info.sampler(0, "FLOAT_2D", "image")
    info.typedef_source(_LIGHT_ICON_TYPEDEF)
    info.vertex_in(0, "VEC2", "pos")
    info.vertex_in(1, "VEC2", "texCoord")
    info.uniform_buf(0, "Data", "g_data")
    info.vertex_out(vert_out)
    info.fragment_out(0, "VEC4", "fragColor")
    info.vertex_source(_LIGHT_ICON_VERT)
    info.fragment_source(_LIGHT_ICON_FRAG)
    shader = gpu.shader.create_from_info(info)
    ubo = gpu.types.GPUUniformBuf(
        gpu.types.Buffer("UBYTE", ctypes.sizeof(UBO_data), UBO_data)
    )
    shader.uniform_block("g_data", ubo)
    return shader, ubo


def _build_border_shader():
    vert_out = gpu.types.GPUStageInterfaceInfo("lls_border_iface")
    vert_out.smooth("VEC2", "texCoord_interp")
    info = gpu.types.GPUShaderCreateInfo()
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.push_constant("VEC4", "color")
    info.push_constant("VEC2", "panel_point_lt")
    info.push_constant("VEC2", "panel_point_rb")
    info.vertex_in(0, "VEC2", "pos")
    info.vertex_source(_BORDER_VERT)
    info.fragment_out(0, "VEC4", "fragColor")
    info.fragment_source(_BORDER_FRAG)
    return gpu.shader.create_from_info(info)


def _ensure_shaders() -> dict:
    """Build the three shaders on first call. No-op afterwards."""
    if _SHADERS:
        return _SHADERS
    _SHADERS["solid"] = gpu.shader.from_builtin("UNIFORM_COLOR")
    icon, ubo = _build_light_icon_shader()
    _SHADERS["light_icon"] = icon
    _SHADERS["light_icon_ubo"] = ubo
    _SHADERS["border"] = _build_border_shader()
    return _SHADERS


# ---------------------------------------------------------------------------
# Equirectangular projection helpers
# ---------------------------------------------------------------------------
#
# The 2D Control Panel is an equirectangular map: x = longitude,
# y = latitude. A LightStudio light is a flat rectangular mesh
# positioned in 3D, perpendicular to the radial direction at its centre,
# pointing back at the world origin. To make the panel preview match
# what Cycles/EEVEE actually renders (see the EXR export for ground
# truth), we project each vertex of the rectangle onto the unit sphere
# and read off (lon, lat) → panel pixel.
#
# This produces the characteristic "bulged" top/bottom edges (corners at
# lower latitude than the middle of the edge) — a per-row 1/cos(lat)
# stretch alone gives a flat-topped trapezoid, which is wrong.
#
# The projection is visual and interactive: hit-testing uses the same
# tessellated warped geometry so click/drag matches the displayed icon.

# Tessellation density for the projected fill / borders. n×n grid → 2n²
# triangles per quad. 20 keeps curves visually smooth even when the top
# edge spans nearly the full panel width.
_EQUIRECT_DIVISIONS = 25


def _make_equirect_projector(panel, center_px_x: float, center_px_y: float):
    """Build a fast closure that projects panel-pixel points on the
    light's local tangent plane to true equirectangular panel pixels.

    The light's centre at ``(center_px_x, center_px_y)`` corresponds to a
    direction ``C`` on the unit sphere. We treat each input point's
    pixel offset from the centre as the (u, v) coordinate on the tangent
    plane at ``C``, build the 3D point ``C + u·E + v·N`` (where E and N
    are the local east/north tangent vectors), then project back through
    ``lon = atan2(P.y, P.x)`` / ``lat = asin(P.z / |P|)``.
    """
    panel_left = panel.point_lt.x
    panel_bot = panel.point_rb.y
    pw = panel.point_rb.x - panel_left
    ph = panel.point_lt.y - panel_bot
    if pw <= 0 or ph <= 0:
        return lambda x, y: (x, y)

    # Per-pixel angular scale.
    rad_per_px_x = 2 * pi / pw
    # Vertical scale is reduced slightly: the icon's logical pixel size
    # is a generous bounding box, but its visible content covers less
    # angular height in the EXR. Shrinking lat-per-pixel here pulls the
    # wrap-band away from the poles to better match the rendered EXR.
    _LAT_SCALE = 0.85
    rad_per_px_y = pi / ph * _LAT_SCALE

    # Centre direction on the unit sphere.
    lon0 = (center_px_x - panel_left) / pw * 2 * pi - pi
    lat0 = (center_px_y - panel_bot) / ph * pi - pi / 2
    cos_lon0, sin_lon0 = cos(lon0), sin(lon0)
    cos_lat0, sin_lat0 = cos(lat0), sin(lat0)

    cx, cy, cz = cos_lat0 * cos_lon0, cos_lat0 * sin_lon0, sin_lat0
    # Local east (longitude tangent) at C.
    ex, ey, ez = -sin_lon0, cos_lon0, 0.0
    # Local north (latitude tangent) at C.
    nx, ny, nz = -sin_lat0 * cos_lon0, -sin_lat0 * sin_lon0, cos_lat0

    def project(px: float, py: float) -> tuple[float, float]:
        # Pixel offset → tangent-plane radians.
        u = (px - center_px_x) * rad_per_px_x
        v = (py - center_px_y) * rad_per_px_y
        # 3D point on the tangent plane to the unit sphere at C.
        Px = cx + u * ex + v * nx
        Py = cy + u * ey + v * ny
        Pz = cz + u * ez + v * nz
        norm = sqrt(Px * Px + Py * Py + Pz * Pz)
        if norm < 1e-9:
            return (px, py)
        lon = atan2(Py, Px)
        lat = asin(max(-1.0, min(1.0, Pz / norm)))
        # Unwrap the longitude relative to the centre so the projected
        # point stays on the same side of the panel as the input. Without
        # this, a vertex slightly past ±π wraps to the opposite edge and
        # tears the mesh.
        d = lon - lon0
        if d > pi:
            lon -= 2 * pi
        elif d < -pi:
            lon += 2 * pi
        out_x = (lon + pi) / (2 * pi) * pw + panel_left
        out_y = (lat + pi / 2) / pi * ph + panel_bot
        return (out_x, out_y)

    return project


def _tessellate_warped_quad(
    verts,
    uvs,
    panel,
    center_x: float,
    n: int = _EQUIRECT_DIVISIONS,
    center_y: float | None = None,
):
    """Bilinearly subdivide a quad into an ``n×n`` grid then project
    each vertex through the true equirectangular projection.

    ``verts`` must be in TRI_STRIP corner order ``(lt, lb, rt, rb)`` —
    the same order produced by :meth:`Rectangle.get_verts`. ``uvs``
    follows the same order or may be ``None`` for un-textured quads
    (e.g. borders). ``center_y`` defaults to the quad's vertical centre.
    Returns ``(positions, tex_coords_or_None, indices)`` ready for
    ``batch_for_shader(..., "TRIS", ..., indices=indices)``.
    """
    lt, lb, rt, rb = verts
    has_uv = uvs is not None
    if has_uv:
        uv_lt, uv_lb, uv_rt, uv_rb = uvs

    if center_y is None:
        center_y = (lt[1] + lb[1] + rt[1] + rb[1]) / 4

    project = _make_equirect_projector(panel, center_x, center_y)

    positions: list[tuple[float, float]] = []
    tex_coords: list[tuple[float, float]] | None = [] if has_uv else None

    for j in range(n + 1):
        ty = j / n  # 0 = bottom edge, 1 = top edge
        lx = lb[0] + (lt[0] - lb[0]) * ty
        ly = lb[1] + (lt[1] - lb[1]) * ty
        rx = rb[0] + (rt[0] - rb[0]) * ty
        ry = rb[1] + (rt[1] - rb[1]) * ty
        if has_uv:
            ulx = uv_lb[0] + (uv_lt[0] - uv_lb[0]) * ty
            uly = uv_lb[1] + (uv_lt[1] - uv_lb[1]) * ty
            urx = uv_rb[0] + (uv_rt[0] - uv_rb[0]) * ty
            ury = uv_rb[1] + (uv_rt[1] - uv_rb[1]) * ty
        for i in range(n + 1):
            tx = i / n
            x = lx + (rx - lx) * tx
            y = ly + (ry - ly) * tx
            positions.append(project(x, y))
            if has_uv:
                tex_coords.append((
                    ulx + (urx - ulx) * tx,
                    uly + (ury - uly) * tx,
                ))

    indices: list[tuple[int, int, int]] = []
    stride = n + 1
    for j in range(n):
        for i in range(n):
            i0 = j * stride + i
            i1 = i0 + 1
            i2 = i0 + stride
            i3 = i2 + 1
            indices.append((i0, i2, i1))
            indices.append((i1, i2, i3))

    return positions, tex_coords, indices


def _point_in_triangle(px: float, py: float, a, b, c) -> bool:
    """Return True when point ``(px, py)`` lies inside triangle ABC."""
    abx = b[0] - a[0]
    aby = b[1] - a[1]
    bcx = c[0] - b[0]
    bcy = c[1] - b[1]
    cax = a[0] - c[0]
    cay = a[1] - c[1]

    apx = px - a[0]
    apy = py - a[1]
    bpx = px - b[0]
    bpy_ = py - b[1]
    cpx = px - c[0]
    cpy = py - c[1]

    cross1 = abx * apy - aby * apx
    cross2 = bcx * bpy_ - bcy * bpx
    cross3 = cax * cpy - cay * cpx
    return (
        (cross1 >= 0 and cross2 >= 0 and cross3 >= 0)
        or (cross1 <= 0 and cross2 <= 0 and cross3 <= 0)
    )


def _warped_outline(
    verts,
    panel,
    center_x: float,
    weight: float,
    n: int = _EQUIRECT_DIVISIONS,
    center_y: float | None = None,
):
    """Return ``(positions, indices)`` for a uniform-thickness outline
    that follows the equirectangular-projected silhouette of a quad.

    The inner ring is the projected boundary of the un-padded quad; the
    outer ring is each inner vertex offset by ``weight`` pixels along
    the local outward normal (computed from screen-space tangents). This
    keeps the selection padding visually constant in pixel thickness
    regardless of latitude — only the inner edge curves with the
    projection.

    ``verts`` must be in TRI_STRIP corner order ``(lt, lb, rt, rb)``.
    """
    lt, lb, rt, rb = verts
    if center_y is None:
        center_y = (lt[1] + lb[1] + rt[1] + rb[1]) / 4

    project = _make_equirect_projector(panel, center_x, center_y)

    # Trace the boundary CCW: bottom → right → top → left. Each side
    # gets ``n`` segments (corners appear once).
    boundary: list[tuple[float, float]] = []
    for i in range(n):
        t = i / n
        boundary.append(project(
            lb[0] + (rb[0] - lb[0]) * t,
            lb[1] + (rb[1] - lb[1]) * t,
        ))
    for j in range(n):
        t = j / n
        boundary.append(project(
            rb[0] + (rt[0] - rb[0]) * t,
            rb[1] + (rt[1] - rb[1]) * t,
        ))
    for i in range(n):
        t = i / n
        boundary.append(project(
            rt[0] + (lt[0] - rt[0]) * t,
            rt[1] + (lt[1] - rt[1]) * t,
        ))
    for j in range(n):
        t = j / n
        boundary.append(project(
            lt[0] + (lb[0] - lt[0]) * t,
            lt[1] + (lb[1] - lt[1]) * t,
        ))

    m = len(boundary)
    outer: list[tuple[float, float]] = []
    for i in range(m):
        prev = boundary[(i - 1) % m]
        nxt = boundary[(i + 1) % m]
        tx = nxt[0] - prev[0]
        ty = nxt[1] - prev[1]
        # CCW boundary → outside is 90° CW from the tangent: (ty, -tx).
        nx_ = ty
        ny_ = -tx
        norm = sqrt(nx_ * nx_ + ny_ * ny_)
        if norm > 1e-6:
            nx_ /= norm
            ny_ /= norm
        outer.append((boundary[i][0] + nx_ * weight, boundary[i][1] + ny_ * weight))

    positions = list(boundary) + outer
    indices: list[tuple[int, int, int]] = []
    for i in range(m):
        i_next = (i + 1) % m
        indices.append((i, m + i, i_next))
        indices.append((m + i, m + i_next, i_next))
    return positions, indices


# ---------------------------------------------------------------------------
# Light-list helpers (also used by the modal operator)
# ---------------------------------------------------------------------------


def send_light_to_bottom(light=None) -> None:
    light = light if light else LightImage.selected_object
    if not light:
        return
    lights = LightImage.lights
    lights.insert(0, lights.pop(lights.index(light)))


def send_light_to_top(light=None) -> None:
    light = light if light else LightImage.selected_object
    if not light:
        return
    lights = LightImage.lights
    lights.append(lights.pop(lights.index(light)))


def fast_3d_edit(light=None) -> None:
    """Invoke ``light_studio.fast_3d_edit`` if registered (step 16)."""
    op = getattr(bpy.ops.light_studio, "fast_3d_edit", None)
    if op is None:
        return
    with contextlib.suppress(RuntimeError):
        op("INVOKE_DEFAULT", continuous=False)


def export_lights_exr(_args=None) -> None:
    """Invoke ``lls.render_lights_exr`` from the control-panel button."""
    op = getattr(bpy.ops.lls, "render_lights_exr", None)
    if op is None:
        return
    with contextlib.suppress(RuntimeError):
        op("INVOKE_DEFAULT")


def _light_brush_label() -> str:
    """Return ``Light Brush [<key>]`` using the registered keymap if any."""
    try:
        from ...handlers.keymaps import get_user_keymap_item  # step 16
        from ..light_brush import OT_LLSFast3DEdit  # step 16

        _, kmi = get_user_keymap_item("Object Mode", OT_LLSFast3DEdit.bl_idname)
        if kmi:
            return f"Light Brush [{kmi.type}]"
    except (ImportError, AttributeError):
        pass
    return "Light Brush [F]"


# ---------------------------------------------------------------------------
# Module-level mutable state used by the modal operator (step 15c)
# ---------------------------------------------------------------------------

view_layers: list = []


# ---------------------------------------------------------------------------
# Button
# ---------------------------------------------------------------------------


class Button(Rectangle):
    """Labelled clickable rectangle.

    Uses ``blf`` for text rendering. Falls back to a stub dimension when
    no GPU context is available (e.g. background-mode tests).
    """

    buttons: list = []

    def __init__(self, loc, text: str, size: int = 15) -> None:
        self.font_size = size
        self.font_color = (0, 0, 0, 1)
        self.bg_color = (0.5, 0.5, 0.5, 1)
        self.bg_color_selected = (0.7, 0.7, 0.7, 1)
        self.font_id = len(Button.buttons)
        self.text = text
        try:
            blf.color(self.font_id, *self.font_color)
            blf.position(self.font_id, loc.x, loc.y, 0)
            blf.size(self.font_id, self.font_size)
            self.dimensions = blf.dimensions(self.font_id, text)
        except (RuntimeError, AttributeError, SystemError):
            # No GPU context (background mode); use a deterministic stub.
            self.dimensions = (len(text) * 8, size)
        self.function = lambda args: None

        super().__init__(loc, self.dimensions[0] + 10, size + 10)
        Button.buttons.append(self)

    def draw(self, mouse_x: float, mouse_y: float) -> None:
        solid = _ensure_shaders()["solid"]
        # Refresh the bound shader state with a no-op draw.
        solid.uniform_float("color", (0, 0, 0, 0))
        batch_for_shader(solid, "POINTS", {"pos": [(0, 0)]}).draw(solid)

        if is_in_rect(self, Vector((mouse_x, mouse_y))):
            solid.uniform_float("color", self.bg_color_selected)
        else:
            solid.uniform_float("color", self.bg_color)
        batch_for_shader(solid, "TRI_STRIP", {"pos": self.get_verts()}).draw(solid)

        blf.size(self.font_id, self.font_size)
        blf.position(self.font_id, self.point_lt.x + 5, self.point_rb.y + 7, 0)
        blf.color(self.font_id, *self.font_color)
        blf.draw(self.font_id, self.text)

    def click(self, args=None):
        return self.function(args)


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------


class Panel(Rectangle):
    """Full-screen control surface housing the X / Send-to-Bottom / Brush buttons."""

    def __init__(self, loc, width: float, height: float) -> None:
        super().__init__(loc, width, height)
        self.button_exit = Button(Vector((0, 0)), "X")
        self.button_exit.function = lambda x: "FINISHED"

        self.button_send_to_bottom = Button(Vector((0, 0)), "Send to Bottom")
        self.button_send_to_bottom.function = send_light_to_bottom

        self.button_fast_3d_edit = Button(Vector((0, 0)), _light_brush_label())
        self.button_fast_3d_edit.function = fast_3d_edit

        self.button_export_exr = Button(Vector((0, 0)), "Export Lights as EXR")
        self.button_export_exr.function = export_lights_exr

        self._move_buttons()

    def _move_buttons(self) -> None:
        self.button_exit.loc = Vector((
            self.point_rb.x - self.button_exit.dimensions[0] / 4,
            self.point_lt.y - self.button_exit.dimensions[1] / 4 + 3,
        ))
        self.button_send_to_bottom.loc = Vector((
            self.point_lt.x + self.button_send_to_bottom.dimensions[0] / 2 + 5,
            self.point_rb.y - self.button_exit.dimensions[1] / 2 - 13,
        ))
        self.button_fast_3d_edit.loc = Vector((
            self.point_lt.x
            + self.button_send_to_bottom.dimensions[0]
            + self.button_fast_3d_edit.dimensions[0] / 2
            + 23,
            self.point_rb.y - self.button_exit.dimensions[1] / 2 - 13,
        ))
        self.button_export_exr.loc = Vector((
            self.point_lt.x
            + self.button_send_to_bottom.dimensions[0]
            + self.button_fast_3d_edit.dimensions[0]
            + self.button_export_exr.dimensions[0] / 2
            + 41,
            self.point_rb.y - self.button_exit.dimensions[1] / 2 - 13,
        ))

    def draw(self) -> None:
        solid = _ensure_shaders()["solid"]

        try:
            from ...ui.preferences import get_panel_bg_color, get_panel_grid_color
            bg_color = get_panel_bg_color()
            grid_color = get_panel_grid_color()
        except Exception:
            bg_color = (0.05, 0.05, 0.05, 1.0)
            grid_color = (0.12, 0.12, 0.12, 1.0)

        solid.uniform_float("color", bg_color)
        batch_for_shader(solid, "TRI_STRIP", {"pos": self.get_verts()}).draw(solid)

        # Faint gray grid
        solid.uniform_float("color", grid_color)
        panel_width = self.point_rb.x - self.point_lt.x
        panel_height = self.point_lt.y - self.point_rb.y
        grid_spacing_x = panel_width / 20
        grid_spacing_y = panel_height / 10

        vertical_lines = []
        for i in range(1, 20):
            x = self.point_lt.x + i * grid_spacing_x
            vertical_lines.extend([(x, self.point_lt.y), (x, self.point_rb.y)])
        if vertical_lines:
            batch_for_shader(solid, "LINES", {"pos": vertical_lines}).draw(solid)

        horizontal_lines = []
        for i in range(1, 10):
            y = self.point_lt.y - i * grid_spacing_y
            horizontal_lines.extend([(self.point_lt.x, y), (self.point_rb.x, y)])
        if horizontal_lines:
            batch_for_shader(solid, "LINES", {"pos": horizontal_lines}).draw(solid)

        # Z-axis guide (blue)
        center_y = (self.point_lt.y + self.point_rb.y) / 2
        solid.uniform_float("color", (0.1, 0.3, 0.8, 0.8))
        batch_for_shader(solid, "LINES", {"pos": [
            (self.point_lt.x + 5, center_y),
            (self.point_rb.x - 5, center_y),
        ]}).draw(solid)

        # Y-axis guides (green, two verticals)
        center_x = (self.point_lt.x + self.point_rb.x) / 2
        left_x = center_x - panel_width / 4
        right_x = center_x + panel_width / 4
        solid.uniform_float("color", (0.2, 0.8, 0.2, 0.8))
        batch_for_shader(solid, "LINES", {"pos": [
            (left_x, self.point_lt.y - 5),
            (left_x, self.point_rb.y),
            (right_x, self.point_lt.y - 5),
            (right_x, self.point_rb.y),
        ]}).draw(solid)

        # X-axis guide (red)
        solid.uniform_float("color", (0.8, 0.2, 0.2, 0.8))
        batch_for_shader(solid, "LINES", {"pos": [
            (center_x, self.point_lt.y - 5),
            (center_x, self.point_rb.y),
        ]}).draw(solid)

        # Panel edges
        batch_for_shader(solid, "LINES", {"pos": [
            (self.point_lt.x, self.point_lt.y),
            (self.point_lt.x, self.point_rb.y),
            (self.point_rb.x, self.point_lt.y),
            (self.point_rb.x, self.point_rb.y),
        ]}).draw(solid)

    def move(self, loc_diff) -> None:
        super().move(loc_diff)
        for light in LightImage.lights:
            light.update_visual_location()
        self._move_buttons()


# ---------------------------------------------------------------------------
# Border
# ---------------------------------------------------------------------------


class Border(Rectangle):
    """Coloured rectangular outline drawn around a :class:`LightImage`."""

    weight = 3

    def __init__(self, light_image: LightImage, color) -> None:
        self.color = color
        self.light_image = light_image
        super().__init__(Vector((0, 0)), 100, 100)

    def get_verts(self):
        self.point_lt = Vector(self.light_image.point_lt)
        self.point_rb = Vector(self.light_image.point_rb)

        self.point_lt.x -= self.weight
        self.point_lt.y += self.weight
        self.point_rb.x += self.weight
        self.point_rb.y -= self.weight

        self.rot = self.light_image.rot
        return super().get_verts()

    def draw(self) -> None:
        shader = _ensure_shaders()["border"]
        # Use the LIGHT's un-padded silhouette as the inner boundary so
        # the outline thickness stays uniform after warping (otherwise
        # inflating by `weight` BEFORE warping makes the strips thicker
        # near the poles where 1/cos(lat) is large).
        light = self.light_image
        light_verts = Rectangle.get_verts(light)
        lleft = min(v[0] for v in light_verts)
        lright = max(v[0] for v in light_verts)
        bleft = light.panel.point_lt.x
        bright = light.panel.point_rb.x

        shader.bind()
        gpu.state.blend_set("ALPHA")
        shader.uniform_float("color", self.color)
        shader.uniform_float("panel_point_lt", light.panel.point_lt)
        shader.uniform_float("panel_point_rb", light.panel.point_rb)

        cx = light.loc.x
        panel = light.panel

        def _draw_outline(verts, offset_x: float = 0.0) -> None:
            positions, indices = _warped_outline(
                verts, panel, cx + offset_x, self.weight,
            )
            batch_for_shader(
                shader, "TRIS", {"pos": positions}, indices=indices,
            ).draw(shader)

        # Always draw three horizontally-tiled copies. Lights near the
        # poles project to a full-360° wrap that overflows the panel in
        # both directions; the shader-side panel clip discards the
        # off-panel pixels so this is cheap and handles the seam case
        # uniformly without special-casing.
        pw = panel.width
        for offset in (-pw, 0.0, pw):
            shifted = [(v[0] + offset, v[1]) for v in light_verts]
            _draw_outline(shifted, offset_x=offset)
        gpu.state.blend_set("NONE")


# ---------------------------------------------------------------------------
# LightImage
# ---------------------------------------------------------------------------


class LightImage(Rectangle):
    """Light thumbnail bound to an LLS_Light collection.

    Reads rotation/scale from the LLS handle hierarchy on every
    :meth:`update_from_lls` call; writes back via :meth:`update_lls`.
    The class-level :attr:`lights` list is the canonical Z-order; the
    modal draw handler iterates it bottom-to-top.
    """

    selected_object: LightImage | None = None
    lights: list = []
    default_size: int = 100

    @classmethod
    def find_idx(cls, lls_light_collection) -> int:
        for idx, light in enumerate(cls.lights):
            if light._collection == lls_light_collection:
                return idx
        return -1

    @classmethod
    def remove(cls, lls_light_collection) -> None:
        idx = cls.find_idx(lls_light_collection)
        if idx >= 0:
            del cls.lights[idx]

    def delete(self) -> None:
        del LightImage.lights[LightImage.lights.index(self)]

    @classmethod
    def refresh(cls) -> None:
        cls.selected_object = None
        for light in list(cls.lights):
            try:
                if light.update_from_lls():
                    light.update_visual_location()
            except ReferenceError:
                light.delete()

    @classmethod
    def change_default_size(cls, value: int) -> None:
        cls.default_size = value
        for light in cls.lights:
            light.width = value * light._scale.x
            light.height = value * light._scale.z

    def panel_loc_to_area_px_lt(self) -> Vector:
        # The EXR camera's equirectangular X axis is mirrored relative
        # to the panel's stored rotation longitude. Apply that mirror,
        # plus the quarter-turn camera offset, only in the visual panel
        # mapping so stored rotations remain unchanged.
        visual_x = (0.25 - self.panel_loc.x) % 1.0
        panel_px_loc = Vector((
            self.panel.width * visual_x,
            -self.panel.height * (1 - self.panel_loc.y),
        ))
        return panel_px_loc + Vector(self.panel.point_lt) - Vector((
            LightImage.default_size * self._scale.x / 2,
            LightImage.default_size * self._scale.z / 2,
        ))

    def _update_panel_loc(self) -> None:
        self.panel_loc.x = (self._lls_rot.x + pi) % (2 * pi) / (2 * pi)
        self.panel_loc.y = fmod(self._lls_rot.y + pi / 2, pi) / pi

    def update_from_lls(self) -> bool:
        if not self._lls_object:
            return False

        if self._lls_object.select_get():
            LightImage.selected_object = self

        updated = False
        if self._lls_rot != self._lls_actuator.rotation_euler:
            updated = True
            self._lls_rot = self._lls_actuator.rotation_euler.copy()
        if self.rot != self._lls_handle.rotation_euler.y:
            updated = True
            self.rot = self._lls_handle.rotation_euler.y
        if self._scale != self._lls_handle.scale:
            updated = True
            self._scale = self._lls_handle.scale.copy()
            self.width = LightImage.default_size * self._scale.x
            self.height = LightImage.default_size * self._scale.z
            basic_obj = self._lls_basic_collection.objects[0]
            basic_obj.data.LLStudio.intensity = basic_obj.data.LLStudio.intensity

        if updated:
            self._update_panel_loc()

        if self._lls_object.type == "MESH":
            tex_node = self._lls_object.active_material.node_tree.nodes["Light Texture"]
            if self._image_path != tex_node.image.filepath:
                updated = True
                self.image = tex_node.image
                self.gpu_texture = gpu.texture.from_image(self.image)
                self._image_path = tex_node.image.filepath

        return updated

    def update_lls(self) -> None:
        self._lls_actuator.rotation_euler = self._lls_rot
        self._lls_handle.rotation_euler.y = self.rot

    @property
    def _lls_object(self):
        light_type = self._lls_handle.LLStudio.type
        try:
            if light_type == "ADVANCED":
                return next(
                    ob for ob in self._lls_handle.children
                    if ob.name.startswith("LLS_LIGHT_MESH")
                )
            if light_type == "BASIC":
                return next(
                    ob for ob in self._lls_handle.children
                    if ob.name.startswith("LLS_LIGHT_AREA")
                )
        except StopIteration as exc:
            raise RuntimeError("Malformed light") from exc
        return None

    def __init__(self, context, panel: Panel, lls_light_collection) -> None:
        self.panel = panel
        self.__panel_loc = Vector((0.5, 0.5))

        self._collection = lls_light_collection
        self._lls_handle = next(
            m for m in lls_light_collection.objects if m.name.startswith("LLS_LIGHT_HANDLE")
        )
        self._lls_actuator = self._lls_object.parent.parent
        self._view_layer = find_view_layer(self._collection, context.view_layer.layer_collection)

        self._lls_basic_collection = next(
            m for m in lls_light_collection.children if m.name.startswith("LLS_Basic")
        )
        self._lls_advanced_collection = next(
            m for m in lls_light_collection.children if m.name.startswith("LLS_Advanced")
        )
        self._basic_view_layer = find_view_layer(
            self._lls_basic_collection, context.view_layer.layer_collection
        )
        self._advanced_view_layer = find_view_layer(
            self._lls_advanced_collection, context.view_layer.layer_collection
        )

        adv_obj = self._lls_advanced_collection.objects[0]
        tex_node = adv_obj.active_material.node_tree.nodes["Light Texture"]
        self.image = tex_node.image
        self.gpu_texture = gpu.texture.from_image(self.image)
        self._image_path = tex_node.image.filepath
        self._lls_rot = None
        self._scale = None

        super().__init__(Vector((0, 0)), LightImage.default_size, LightImage.default_size)
        self.update_from_lls()
        self.update_visual_location()

        LightImage.lights.append(self)

        self.default_border = Border(self, (0.2, 0.35, 0.2, 1))
        self.mute_border = Border(self, (0.7, 0, 0, 1))
        self.select_border = Border(self, (0.2, 0.9, 0.2, 1))
        self.active_border = Border(self, (0.1, 0.45, 0.1, 1))

    @property
    def mute(self) -> bool:
        return self._view_layer.exclude

    @mute.setter
    def mute(self, exclude: bool) -> None:
        self._view_layer.exclude = exclude
        if not exclude:
            self._lls_handle.LLStudio.type = self._lls_handle.LLStudio.type

    @property
    def panel_loc(self) -> Vector:
        return self.__panel_loc

    @panel_loc.setter
    def panel_loc(self, pos) -> None:
        self.__panel_loc = pos
        self._lls_rot = Vector((
            (self.panel_loc.x - 0.5) * (2 * pi),
            (self.panel_loc.y - 0.5) * pi,
            self._lls_rot.z,
        ))
        self.update_visual_location()

    def select(self) -> None:
        if self.mute:
            return
        bpy.ops.object.select_all(action="DESELECT")
        self._lls_handle.LLStudio.type = self._lls_handle.LLStudio.type
        bpy.context.view_layer.objects.active = self._lls_object
        self._lls_object.select_set(True)

    def is_mouse_over(self, mouse_x: float, mouse_y: float) -> bool:
        bleft = self.panel.point_lt.x
        bright = self.panel.point_rb.x

        if mouse_x > bright or mouse_x < bleft:
            return False

        verts = self.get_verts()
        cx = self.loc.x
        pw = self.panel.width

        for offset in (-pw, 0.0, pw):
            shifted = deepcopy(verts)
            for v in shifted:
                v[0] += offset
            positions, _tex_coords, indices = _tessellate_warped_quad(
                shifted, None, self.panel, cx + offset,
            )

            min_x = min(p[0] for p in positions)
            max_x = max(p[0] for p in positions)
            min_y = min(p[1] for p in positions)
            max_y = max(p[1] for p in positions)
            if not (min_x <= mouse_x <= max_x and min_y <= mouse_y <= max_y):
                continue

            for i0, i1, i2 in indices:
                if _point_in_triangle(
                    mouse_x, mouse_y,
                    positions[i0], positions[i1], positions[i2],
                ):
                    return True
        return False

    def _push_advanced_inputs(self, lls_node) -> None:
        """Copy 21 advanced shader inputs from the Group node into UBO_data."""
        UBO_data.intensity = lls_node.inputs["Intensity"].default_value
        UBO_data.exposure = lls_node.inputs["Exposure"].default_value
        UBO_data.texture_switch = lls_node.inputs["Texture Switch"].default_value
        color_overlay = lls_node.inputs["Color Overlay"].default_value
        UBO_data.color_overlay = (ctypes.c_float * len(color_overlay))(*color_overlay)
        UBO_data.color_saturation = lls_node.inputs["Color Saturation"].default_value
        UBO_data.mask_bottom_to_top = lls_node.inputs["Mask - Bottom to Top"].default_value
        UBO_data.mask_diagonal_bottom_left = lls_node.inputs["Mask - Diagonal Bottom Left"].default_value
        UBO_data.mask_diagonal_bottom_right = lls_node.inputs["Mask - Diagonal Bottom Right"].default_value
        UBO_data.mask_diagonal_top_left = lls_node.inputs["Mask - Diagonal Top Left"].default_value
        UBO_data.mask_diagonal_top_right = lls_node.inputs["Mask - Diagonal Top Right"].default_value
        UBO_data.mask_gradient_amount = lls_node.inputs["Mask - Gradient Amount"].default_value
        UBO_data.mask_gradient_switch = lls_node.inputs["Mask - Gradient Switch"].default_value
        UBO_data.mask_gradient_type = lls_node.inputs["Mask - Gradient Type"].default_value
        UBO_data.mask_left_to_right = lls_node.inputs["Mask - Left to Right"].default_value
        UBO_data.mask_right_to_left = lls_node.inputs["Mask - Right to Left"].default_value
        UBO_data.mask_ring_inner_radius = lls_node.inputs["Mask - Ring Inner Radius"].default_value
        UBO_data.mask_ring_outer_radius = lls_node.inputs["Mask - Ring Outer Radius"].default_value
        UBO_data.mask_ring_switch = lls_node.inputs["Mask - Ring Switch"].default_value
        UBO_data.mask_top_to_bottom = lls_node.inputs["Mask - Top to Bottom"].default_value

    def draw(self) -> None:
        try:
            select = self._lls_object.select_get()
            active_select = self._lls_object == bpy.context.active_object
        except ReferenceError:
            return
        except AttributeError:
            select = False
            active_select = False

        shaders = _ensure_shaders()
        solid = shaders["solid"]
        light_icon = shaders["light_icon"]

        # No-op draw to refresh state.
        solid.uniform_float("color", (0, 0, 0, 0))
        batch_for_shader(solid, "POINTS", {"pos": [(0, 0)]}).draw(solid)

        bleft = self.panel.point_lt.x
        bright = self.panel.point_rb.x
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

        light_icon.bind()
        UBO_data.panel_point_lt = (ctypes.c_float * 2)(*self.panel.point_lt)
        UBO_data.panel_point_rb = (ctypes.c_float * 2)(*self.panel.point_rb)

        if self._lls_handle.LLStudio.type == "ADVANCED":
            light_icon.uniform_bool("advanced", [True])
            light_icon.uniform_sampler("image", self.gpu_texture)
            try:
                lls_node = self._lls_object.active_material.node_tree.nodes["Group"]
                self._push_advanced_inputs(lls_node)
            except (KeyError, AttributeError):
                # Material missing the Group node; render with whatever is in UBO.
                pass
        else:
            light_icon.uniform_bool("advanced", [False])
            UBO_data.intensity = self._lls_object.data.LLStudio.intensity
            UBO_data.color_saturation = self._lls_object.data.LLStudio.color_saturation
            v = Vector(self._lls_object.data.LLStudio.color[:] + (1,))
            UBO_data.color_overlay = (ctypes.c_float * len(v))(*v)

        gpu.state.blend_set("ALPHA")
        ubo = gpu.types.GPUUniformBuf(
            gpu.types.Buffer("UBYTE", ctypes.sizeof(UBO_data), UBO_data)
        )
        light_icon.uniform_block("g_data", ubo)

        # Light's panel-space center X (un-warped logical position).
        # The warp pivots around this so a light's centre stays put while
        # its silhouette widens horizontally as it approaches the poles.
        cx = self.loc.x

        def _draw_icon(pos, offset_x: float = 0.0):
            positions, tex_coords, indices = _tessellate_warped_quad(
                pos, uv_coords, self.panel, cx + offset_x,
            )
            batch_for_shader(
                light_icon,
                "TRIS",
                {"pos": positions, "texCoord": tex_coords},
                indices=indices,
            ).draw(light_icon)

        # Always draw three horizontally-tiled copies (-pw, 0, +pw).
        # Polar lights wrap a full 360° of longitude, which overflows
        # the panel on both sides; the shader-side panel clip handles
        # the off-panel pixels. Subsumes the seam-crossing case too.
        pw = self.panel.width
        for offset in (-pw, 0.0, pw):
            shifted = deepcopy(verts)
            for v in shifted:
                v[0] += offset
            _draw_icon(shifted, offset_x=offset)
        gpu.state.blend_set("NONE")

    def update_visual_location(self) -> None:
        self.loc = self.panel_loc_to_area_px_lt() + Vector((self.width / 2, self.height / 2))

    def move(self, loc_diff) -> None:
        super().move(loc_diff)
        visual_x = (self.loc.x - self.panel.loc.x) / self.panel.width + 0.5
        # Inverse of the mirrored quarter-turn visual mapping in
        # panel_loc_to_area_px_lt.
        self.panel_loc = Vector((
            (0.25 - visual_x) % 1.0,
            clamp(0.0001, (self.loc.y - self.panel.loc.y) / self.panel.height + 0.5, 0.9999),
        ))
        self.update_lls()
