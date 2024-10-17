#Created by Styriam sp. z o.o.

bl_info = {
    "name": "LeoMoon LightStudio",
    "description": "Easy setup for complex studio lighting",
    "author": "LeoMoon Studios",
    "version": (2, 15, 3),
    "blender": (3, 2, 2),
    "location": "View3D -> Tools -> LightStudio",
    "wiki_url": "",
    "category": "User Interface" }


import bpy

# load and reload submodules
##################################

from . import auto_load

auto_load.init()


# register
##################################

from . light_operators import LeoMoon_Light_Studio_Properties, LeoMoon_Light_Studio_Object_Properties, LeoMoon_Light_Studio_Light_Properties
from . import deleteOperator, light_brush
from . operators import modal
from . import light_operators

def register():
    auto_load.register()
    bpy.types.Object.protected = bpy.props.BoolProperty(name = 'protected', default = False)
    bpy.types.Scene.LLStudio = bpy.props.PointerProperty(name="LeoMoon LightStudio Properties", type = LeoMoon_Light_Studio_Properties)
    bpy.types.Object.LLStudio = bpy.props.PointerProperty(name="LeoMoon LightStudio Object Properties", type = LeoMoon_Light_Studio_Object_Properties)
    bpy.types.Light.LLStudio = bpy.props.PointerProperty(name="LeoMoon LightStudio Light Properties", type = LeoMoon_Light_Studio_Light_Properties)
    deleteOperator.add_shortkeys()
    light_brush.add_shortkeys()
    modal.add_shortkeys()
    light_operators.add_shortkeys()
    bpy.app.handlers.load_post.append(modal.load_handler)
    bpy.app.handlers.frame_change_pre.append(modal.frame_change_handler)


def unregister():
    deleteOperator.remove_shortkeys()
    light_brush.remove_shortkeys()
    modal.remove_shortkeys()
    light_operators.remove_shortkeys()
    auto_load.unregister()
    bpy.app.handlers.load_post.remove(modal.load_handler)
    bpy.app.handlers.frame_change_pre.remove(modal.frame_change_handler)
