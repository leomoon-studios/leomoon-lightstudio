'''
Copyright (C) 2015 Marcin Zielinski
martin.zielinsky at gmail.com

Created by Marcin Zielinski

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

bl_info = {
    "name": "Blender Light Studio",
    "description": "Easy setup for complex studio lighting",
    "author": "LeoMoon Studios, Marcin Zielinski, special thanks to Maciek Ptaszynski for initial scene",
    "version": (2, 3, 6),
    "blender": (2, 78, 0),
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

from . light_operators import Blender_Light_Studio_Properties
from . import deleteOperator
from . import selectOperator
from . import light_preview_list
def register():
    try: bpy.utils.register_module(__name__)
    except: traceback.print_exc()
    bpy.types.Scene.BLStudio = bpy.props.PointerProperty(name="Blender Light Studio Properties", type = Blender_Light_Studio_Properties)
    bpy.types.Object.protected = bpy.props.BoolProperty(name = 'protected', default = False)
    selectOperator.add_shortkeys()
    deleteOperator.add_shortkeys()
    light_preview_list.register()
    
    print("Registered {} with {} modules".format(bl_info["name"], len(modules)))
    

def unregister():
    selectOperator.remove_shortkeys()
    deleteOperator.remove_shortkeys()
    try: bpy.utils.unregister_module(__name__)
    except: traceback.print_exc()
    
    print("Unregistered {}".format(bl_info["name"]))
    