#Created by Striam Sp. z o.o.

bl_info = {
    "name": "LeoMoon LightStudio",
    "description": "Easy setup for complex studio lighting",
    "author": "LeoMoon Studios",
    "version": (2, 4, 0),
    "blender": (2, 80, 0),
    "location": "View3D -> Tools -> Light Studio",
    "wiki_url": "",
    "category": "User Interface" }
    
    
import bpy      

# load and reload submodules
##################################    

from . import auto_load

auto_load.init()


# register
################################## 

from . light_operators import Blender_Light_Studio_Properties
from . import deleteOperator
from . import light_preview_list

def register():
    auto_load.register()

    bpy.types.Scene.BLStudio = bpy.props.PointerProperty(name="Blender Light Studio Properties", type = Blender_Light_Studio_Properties)
    bpy.types.Object.protected = bpy.props.BoolProperty(name = 'protected', default = False)
    deleteOperator.add_shortkeys()
    light_preview_list.register()
    

def unregister():
    deleteOperator.remove_shortkeys()
    auto_load.unregister()
