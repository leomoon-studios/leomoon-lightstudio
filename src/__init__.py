#Created by Striam Sp. z o.o.

bl_info = {
    "name": "LeoMoon LightStudio",
    "description": "Easy setup for complex studio lighting",
    "author": "LeoMoon Studios",
    "version": (2, 6, 0),
    "blender": (2, 80, 0),
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

from . light_operators import LeoMoon_Light_Studio_Properties, LeoMoon_Light_Studio_Object_Properties
from . import deleteOperator

def register():
    auto_load.register()
    bpy.types.Object.protected = bpy.props.BoolProperty(name = 'protected', default = False)
    bpy.types.Scene.LLStudio = bpy.props.PointerProperty(name="LeoMoon LightStudio Properties", type = LeoMoon_Light_Studio_Properties)
    bpy.types.Object.LLStudio = bpy.props.PointerProperty(name="LeoMoon LightStudio Object Properties", type = LeoMoon_Light_Studio_Object_Properties)
    deleteOperator.add_shortkeys()
    

def unregister():
    deleteOperator.remove_shortkeys()
    auto_load.unregister()
