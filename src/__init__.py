#Created by Striam Sp. z o.o.

bl_info = {
    "name": "LeoMoon LightStudio",
    "description": "Easy setup for complex studio lighting",
    "author": "LeoMoon Studios",
    "version": (2, 3, 11),
    "blender": (2, 79, 0),
    "location": "View3D -> Tools -> Light Studio",
    "wiki_url": "",
    "category": "User Interface" }
    
    
import bpy      

# load and reload submodules
##################################    
    
from . import developer_utils
modules = developer_utils.setup_addon_modules(__path__, __name__, "bpy" in locals())



# register
################################## 

import traceback

from . light_operators import Blender_Light_Studio_Properties, update_selection_override
from . import deleteOperator
from . import selectOperator
from . import light_preview_list

def config_load():
    from extensions_framework import util as efutil
    bpy.bls_selection_override_right = efutil.find_config_value(bl_info['name'], 'defaults', 'selection_override_right', True)
    bpy.bls_selection_override_left = efutil.find_config_value(bl_info['name'], 'defaults', 'selection_override_left', False)
    
    update_selection_override()
    
def register():
    try: bpy.utils.register_module(__name__)
    except: traceback.print_exc()
    bpy.types.Scene.BLStudio = bpy.props.PointerProperty(name="Blender Light Studio Properties", type = Blender_Light_Studio_Properties)
    bpy.types.Object.protected = bpy.props.BoolProperty(name = 'protected', default = False)
    deleteOperator.add_shortkeys()
    config_load() # select operator shortkeys
    light_preview_list.register()
    
    
    print("Registered {} with {} modules".format(bl_info["name"], len(modules)))
    

def unregister():
    selectOperator.remove_shortkeys()
    deleteOperator.remove_shortkeys()
    try: bpy.utils.unregister_module(__name__)
    except: traceback.print_exc()
    
    print("Unregistered {}".format(bl_info["name"]))
    
