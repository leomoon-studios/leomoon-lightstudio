import os
import bpy
from . common import getLightMesh, isFamily

_ = os.sep
    
def enum_previews_from_directory_items(self, context):
    """EnumProperty callback"""
    enum_items = []

    if context is None:
        return enum_items

    wm = context.window_manager
    
    script_file = os.path.realpath(__file__)
    dir = os.path.dirname(script_file)
    directory=os.path.join(dir,"textures_real_lights"+_)

    # Get the preview collection (defined in register func).
    pcoll = preview_collections["main"]

    if not pcoll.updated:
        return pcoll.tex_previews

    print("Scanning directory: %s" % directory)

    if directory and os.path.exists(directory):
        # Scan the directory for png files
        image_paths = []
        for fn in os.listdir(directory):
            if os.path.splitext(fn)[1] in (".tif", ".exr", ".hdr"):
                image_paths.append(fn)

        for i, name in enumerate(image_paths):
            # generates a thumbnail preview for a file.
            filepath = os.path.join(directory, name)
            thumb = pcoll.load(filepath, filepath, 'IMAGE')
            basename = os.path.splitext(name)[0]
            enum_items.append((name, basename, name, thumb.icon_id, i))

    pcoll.tex_previews = enum_items
    pcoll.updated = False
    return pcoll.tex_previews


# We can store multiple preview collections here,
# however in this example we only store "main"
preview_collections = {}

def preview_enum_get(wm):
    nodes = getLightMesh().active_material.node_tree.nodes
    if not "Light Texture" in nodes:
        return -1
    
    tex = nodes["Light Texture"].image.filepath
    tex = os.path.split(tex)[1]
    names = (p[0] for p in preview_collections["main"].tex_previews)
    
    for i, name in enumerate(names):
        if name == tex:
            return i
    return -1
    
def preview_enum_set(wm, context):
    print("Set preview = %s" % context)
    name = preview_collections["main"].tex_previews[context][0]
    
    light = getLightMesh()
    script_file = os.path.realpath(__file__)
    dir = os.path.dirname(script_file)
    directory=os.path.join(dir,"textures_real_lights"+_)
    light.active_material.node_tree.nodes["Light Texture"].image.filepath = directory + name
    
    return None

def register():
    from bpy.types import WindowManager
    from bpy.props import EnumProperty

    WindowManager.bls_tex_previews = EnumProperty(
            items=enum_previews_from_directory_items,
            get=preview_enum_get,
            set=preview_enum_set,
            )

    import bpy.utils.previews
    pcoll = bpy.utils.previews.new()
    pcoll.bls_tex_previews = ()
    pcoll.updated = True

    preview_collections["main"] = pcoll


def unregister():
    from bpy.types import WindowManager

    del WindowManager.bls_tex_previews

    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()
