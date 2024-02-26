import bpy
from . common import family
from . operators import VERBOSE
import os

class LightDict:
    _dict = {
        "advanced": {
            "tex": "Soft Box A.exr",
            "Texture Switch": 1.0,
            "Color Overlay": [
                1.0,
                0.4000000059604645,
                0.15000000596046448,
                1.0
            ],
            "Color Saturation": 0.0,
            "Intensity": 2.0,
            "Exposure": 1.0,
            "Mask - Gradient Switch": 0.0,
            "Mask - Gradient Type": 0.0,
            "Mask - Gradient Amount": 0.0,
            "Mask - Ring Switch": 0.0,
            "Mask - Ring Inner Radius": 0.0,
            "Mask - Ring Outer Radius": 0.0,
            "Mask - Top to Bottom": 0.0,
            "Mask - Bottom to Top": 0.0,
            "Mask - Left to Right": 0.0,
            "Mask - Right to Left": 0.0,
            "Mask - Diagonal Top Left": 0.0,
            "Mask - Diagonal Top Right": 0.0,
            "Mask - Diagonal Bottom Right": 0.0,
            "Mask - Diagonal Bottom Left": 0.0,
            "Mask - Backface": 0.0
        },
        "basic": {
            "color": [
                1.0,
                1.0,
                1.0
            ],
            "color_saturation": 0.0,
            "intensity": 2.0,
        },
        "light_name": "",
        "order_index": 0,
        "radius": 30.0,
        "position": [
            0.0,
            0.0
        ],
        "rotation": 0.0,
        "scale": [
            1.0,
            1.0,
            1.0
        ],
        "type": "ADVANCED"
    }

    def __init__(self, real_dict=None):
        import copy
        self.dict = copy.deepcopy(self._dict)

        if real_dict:
            self.dict.update(real_dict)

    def __getitem__(self, key):
        return self.dict[key]

    def __setitem__(self, key, val):
        self.dict[key] = val

    def __str__(self):
        import json
        return json.dumps(self.dict, indent=4, separators=(',', ': '))

class InvalidLight(Exception):
    pass

def salvage_data(lls_collection, only_validate=False):
    # Salvage data
    objects = [ob for ob in lls_collection.objects]
    light_handle = [ob for ob in objects if ob.name.startswith("LLS_LIGHT.")]
    if light_handle: light_handle = light_handle[0]
    family_obs = family(light_handle)

    lls_mesh = [ob for ob in family_obs if ob.name.startswith("LLS_LIGHT_MESH")]
    if lls_mesh: lls_mesh = lls_mesh[0]

    lls_basic = [ob for ob in family_obs if ob.name.startswith("LLS_LIGHT_AREA")]
    if lls_basic: lls_basic = lls_basic[0]

    lls_handle = [ob for ob in family_obs if ob.name.startswith("LLS_LIGHT_HANDLE")]
    if lls_handle: lls_handle = lls_handle[0]

    # old version
    light = LightDict()
    if lls_mesh:
        # Include obsolete values. Newer lls_handle will override them (if found)
        try:
            light['light_name'] = lls_mesh.LLStudio.light_name
            light['order_index'] = lls_mesh.LLStudio.order_index
            light['radius'] = lls_mesh.location.x
            light['position'] = [lls_mesh.parent.rotation_euler.x, lls_mesh.parent.rotation_euler.y]
            light['rotation'] = -lls_mesh.rotation_euler.x
            light['type'] = 'ADVANCED'

            light['light_name'] = lls_mesh.LLStudio.light_name
            light['order_index'] = lls_mesh.LLStudio.order_index

            light['scale'] = [lls_mesh.scale.y, lls_mesh.scale.x, lls_mesh.scale.z]

            # advanced
            texpath = lls_mesh.material_slots[0].material.node_tree.nodes["Light Texture"].image.filepath
            light['advanced']['tex'] = texpath.split(bpy.path.native_pathsep("\\textures_real_lights\\"))[-1]

            mat_nodes = lls_mesh.active_material.node_tree.nodes
            try:
                light['advanced']['Texture Switch'] = mat_nodes["Group"].inputs['Texture Switch'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Texture Switch)")
            
            try:
                light['advanced']['Color Overlay'] = [mat_nodes["Group"].inputs['Color Overlay'].default_value[0],
                                    mat_nodes["Group"].inputs['Color Overlay'].default_value[1],
                                    mat_nodes["Group"].inputs['Color Overlay'].default_value[2],
                                    mat_nodes["Group"].inputs['Color Overlay'].default_value[3]]
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Color Overlay)")
            
            try:
                light['advanced']['Color Saturation'] = mat_nodes["Group"].inputs['Color Saturation'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Color Saturation)")
            
            try:
                light['advanced']['Intensity'] = mat_nodes["Group"].inputs['Intensity'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Intensity)")
            
            try:
                light['advanced']['Exposure'] = mat_nodes["Group"].inputs['Exposure'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Exposure)")
            
            try:
                light['advanced']['Mask - Gradient Switch'] = mat_nodes["Group"].inputs['Mask - Gradient Switch'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Mask - Gradient Switch)")
            
            try:
                light['advanced']['Mask - Gradient Type'] = mat_nodes["Group"].inputs['Mask - Gradient Type'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Mask - Gradient Type)")
            
            try:
                light['advanced']['Mask - Gradient Amount'] = mat_nodes["Group"].inputs['Mask - Gradient Amount'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Mask - Gradient Amount)")
            
            try:
                light['advanced']['Mask - Ring Switch'] = mat_nodes["Group"].inputs['Mask - Ring Switch'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Mask - Ring Switch)")
            
            try:
                light['advanced']['Mask - Ring Inner Radius'] = mat_nodes["Group"].inputs['Mask - Ring Inner Radius'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Mask - Ring Inner Radius)")
            
            try:
                light['advanced']['Mask - Ring Outer Radius'] = mat_nodes["Group"].inputs['Mask - Ring Outer Radius'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Mask - Ring Outer Radius)")
            
            try:
                light['advanced']['Mask - Top to Bottom'] = mat_nodes["Group"].inputs['Mask - Top to Bottom'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Mask - Top to Bottom)")
            
            try:
                light['advanced']['Mask - Bottom to Top'] = mat_nodes["Group"].inputs['Mask - Bottom to Top'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Mask - Bottom to Top)")
            
            try:
                light['advanced']['Mask - Left to Right'] = mat_nodes["Group"].inputs['Mask - Left to Right'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Mask - Left to Right)")
            
            try:
                light['advanced']['Mask - Right to Left'] = mat_nodes["Group"].inputs['Mask - Right to Left'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Mask - Right to Left)")
            
            try:
                light['advanced']['Mask - Diagonal Top Left'] = mat_nodes["Group"].inputs['Mask - Diagonal Top Left'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Mask - Diagonal Top Left)")
                
            
            try:
                light['advanced']['Mask - Diagonal Top Right'] = mat_nodes["Group"].inputs['Mask - Diagonal Top Right'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Mask - Diagonal Top Right)")
            
            try:
                light['advanced']['Mask - Diagonal Bottom Right'] = mat_nodes["Group"].inputs['Mask - Diagonal Bottom Right'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Mask - Diagonal Bottom Right)")
            
            try:
                light['advanced']['Mask - Diagonal Bottom Left'] = mat_nodes["Group"].inputs['Mask - Diagonal Bottom Left'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Mask - Diagonal Bottom Left)")
            
            try:
                light['advanced']['Mask - Backface'] = mat_nodes["Group"].inputs['Mask - Backface'].default_value
            except:
                if only_validate: raise InvalidLight()
                print("Error while parsing Mesh Light (Mask - Backface)")
            
        except:
            if only_validate: raise InvalidLight()
            print("Error while parsing Mesh Light")

    if lls_handle:
        try:
            light['light_name'] = lls_handle.LLStudio.light_name
            light['order_index'] = lls_handle.LLStudio.order_index
            light['radius'] = lls_handle.location.z
            light['position'] = [lls_handle.parent.rotation_euler.x, lls_handle.parent.rotation_euler.y]
            light['rotation'] = lls_handle.rotation_euler.y
            light['scale'] = lls_handle.scale[:]
            light['type'] = lls_handle.LLStudio.type
            lls_handle.constraints["Child Of"].inverse_matrix
        except:
            if only_validate: raise InvalidLight()
            print("Handled error while parsing lls_handle")

    if lls_basic:
        try:
            light['basic']['color'] = [lls_basic.data.LLStudio.color.r, lls_basic.data.LLStudio.color.g, lls_basic.data.LLStudio.color.b]
            light['basic']['color_saturation'] = lls_basic.data.LLStudio.color_saturation
            light['basic']['intensity'] = lls_basic.data.LLStudio.intensity
        except:
            if only_validate: raise InvalidLight()
            print("Handled error while parsing Light Handle")
    else:
        try:
            light['basic']['color'] = light['advanced']['Color Overlay'][:3]
            light['basic']['color_saturation'] = light['advanced']['Color Saturation']
            light['basic']['intensity'] = light['advanced']['Intensity']
        except:
            if only_validate: raise InvalidLight()
            print("Handled error while parsing Area Light")

    if VERBOSE: print(light)
    return light

def light_from_dict(from_dict, profile_collection):
    if isinstance(from_dict, dict):
        light_dict = LightDict(from_dict)
        if not 'basic' in from_dict:
            light_dict['basic']['color'] = light_dict['advanced']['Color Overlay'][:3]
            light_dict['basic']['color_saturation'] = light_dict['advanced']['Color Saturation']
            light_dict['basic']['intensity'] = light_dict['advanced']['Intensity']
            if VERBOSE:
                print('_'*5, 'LightDict', '_'*5)
                print(light_dict)
        if not 'order_index' in from_dict:
            light_dict['order_index'] = None
    else:
        light_dict = from_dict

    profile_empty = [ob for ob in profile_collection.objects if ob.name.startswith('LLS_PROFILE')][0]
    # before
    A = set(profile_empty.children)

    bpy.ops.scene.add_leomoon_studio_light()
    print(f"Added light: {light_dict['light_name']}")

    # after operation
    B = set(profile_empty.children)

    # whats the difference
    lgrp = (A ^ B).pop()

    actuator = [c for c in family(lgrp) if "LLS_ROTATION" in c.name][0]
    lhandle = [c for c in family(lgrp) if "LLS_LIGHT_HANDLE" in c.name][0]
    ladvanced_object = [c for c in family(lgrp) if "LLS_LIGHT_MESH" in c.name][0]
    lbasic_object = [c for c in family(lgrp) if "LLS_LIGHT_AREA" in c.name][0]

    lhandle.location.z = light_dict['radius']
    lhandle.rotation_euler.y = light_dict['rotation']

    actuator.rotation_euler.x = light_dict['position'][0]
    actuator.rotation_euler.y = light_dict['position'][1]
    actuator.rotation_euler.z = 0

    lhandle.LLStudio.light_name = light_dict['light_name']
    if light_dict['order_index'] is not None:
        lhandle.LLStudio.order_index = light_dict['order_index']
    lhandle.scale = light_dict['scale']

    lhandle.LLStudio.type = 'BASIC'

    try:
        bpy.context.view_layer.objects.active = lbasic_object
    except RuntimeError:
        print('error')
    lbasic_object.data.LLStudio.color = light_dict['basic']['color']

    lbasic_object.data.LLStudio.color_saturation = light_dict['basic']['color_saturation']
    lbasic_object.data.LLStudio.intensity = light_dict['basic']['intensity']

    lhandle.LLStudio.type = light_dict['type']

    # Advanced
    new_mat_nodes = ladvanced_object.material_slots[0].material.node_tree.nodes
    new_mat_nodes["Group"].inputs[2].default_value = light_dict['advanced']['Texture Switch']
    new_mat_nodes["Group"].inputs[3].default_value[0] = light_dict['advanced']['Color Overlay'][0]
    new_mat_nodes["Group"].inputs[3].default_value[1] = light_dict['advanced']['Color Overlay'][1]
    new_mat_nodes["Group"].inputs[3].default_value[2] = light_dict['advanced']['Color Overlay'][2]
    new_mat_nodes["Group"].inputs[3].default_value[3] = light_dict['advanced']['Color Overlay'][3]
    new_mat_nodes["Group"].inputs[4].default_value = light_dict['advanced']['Color Saturation']
    new_mat_nodes["Group"].inputs[5].default_value = light_dict['advanced']['Intensity']
    new_mat_nodes["Group"].inputs[6].default_value = light_dict['advanced']['Exposure']
    new_mat_nodes["Group"].inputs[7].default_value = light_dict['advanced']['Mask - Gradient Switch']
    new_mat_nodes["Group"].inputs[8].default_value = light_dict['advanced']['Mask - Gradient Type']
    new_mat_nodes["Group"].inputs[9].default_value = light_dict['advanced']['Mask - Gradient Amount']
    new_mat_nodes["Group"].inputs[10].default_value = light_dict['advanced']['Mask - Ring Switch']
    new_mat_nodes["Group"].inputs[11].default_value = light_dict['advanced']['Mask - Ring Inner Radius']
    new_mat_nodes["Group"].inputs[12].default_value = light_dict['advanced']['Mask - Ring Outer Radius']
    new_mat_nodes["Group"].inputs[13].default_value = light_dict['advanced']['Mask - Top to Bottom']
    new_mat_nodes["Group"].inputs[14].default_value = light_dict['advanced']['Mask - Bottom to Top']
    new_mat_nodes["Group"].inputs[15].default_value = light_dict['advanced']['Mask - Left to Right']
    new_mat_nodes["Group"].inputs[16].default_value = light_dict['advanced']['Mask - Right to Left']
    new_mat_nodes["Group"].inputs[17].default_value = light_dict['advanced']['Mask - Diagonal Top Left']
    new_mat_nodes["Group"].inputs[18].default_value = light_dict['advanced']['Mask - Diagonal Top Right']
    new_mat_nodes["Group"].inputs[19].default_value = light_dict['advanced']['Mask - Diagonal Bottom Right']
    new_mat_nodes["Group"].inputs[20].default_value = light_dict['advanced']['Mask - Diagonal Bottom Left']
    new_mat_nodes["Group"].inputs[21].default_value = light_dict['advanced']['Mask - Backface']

    script_file = os.path.realpath(__file__)
    dir = os.path.dirname(script_file)
    if os.path.isabs(light_dict['advanced']['tex']):
        new_mat_nodes["Light Texture"].image.filepath = light_dict['advanced']['tex']
    else:
        new_mat_nodes["Light Texture"].image.filepath = os.path.join(dir, "textures_real_lights", light_dict['advanced']['tex'])


def convert_old_light(lls_mesh, profile_collection):
    # Salvage data
    col = lls_mesh.users_collection[0]

    light = salvage_data(col)
    if VERBOSE: print(light)

    # Some crucial objects are missing. Delete whole light collection

    from . light_operators import _delete_leomoon_studio_light
    if hasattr(lls_mesh, 'use_fake_user'):
        lls_mesh.use_fake_user = False
    try:
        _delete_leomoon_studio_light(bpy.context, lls_mesh)
    except Exception as e:
        import traceback 
        traceback.print_exc()
    
    light_from_dict(light, profile_collection)