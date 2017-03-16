def isFamily(ob=None):
    if not ob:
        ob = bpy.context.scene.objects.active

    if ob.name.startswith('BLENDER_LIGHT_STUDIO'): return True
    if not ob.name.startswith('BLS_'): return False
    while ob.parent:
        ob = ob.parent
        if ob.name.startswith('BLENDER_LIGHT_STUDIO'): return True
    
    return False

def family(object):
    ''' Object + Grand children without ancestors '''
    family = [object.children[:]+(object,)]
      
    def rec(object, family):
        family[0] += object.children
        for ob in object.children:
            rec(ob, family)
        
    for ob in object.children:
        rec(ob, family)
        
    return family.pop()

def findLightGrp(ob):
    while ob.parent:
        ob = ob.parent
        if ob.name.startswith('BLS_LIGHT_GRP.'): return ob
    return None

def getLightMesh():
    #obs = bpy.context.scene.objects
    #lightGrp = obs.active
    #light_no = lightGrp.name.split('.')[1]
    #return obs[obs.find('BLS_LIGHT_MESH.'+light_no)]

    lg = findLightGrp(bpy.context.scene.objects.active)
    lm = [l for l in family(lg) if l.name.startswith("BLS_LIGHT_MESH")]
    return lm[0] if len(lm) else None

def getLightController():
    obs = bpy.context.scene.objects
    lightGrp = obs.active
    light_no = lightGrp.name.split('.')[1]
    return obs[obs.find('BLS_CONTROLLER.'+light_no)]


def findLightProfile(ob):
    while ob.parent:
        ob = ob.parent
        if ob.name.startswith('BLS_PROFILE'): return ob
    return None

def getLightHandle(ob=None):
    if not ob:
        ob = bpy.context.scene.objects.active

    p = findLightProfile(ob)
    if not p:
        return None
    
    h = [h for h in p.children if h.name.startswith('BLS_HANDLE')]
    if len(h):
        return h[0]
    else:
        return None

import bpy
def refreshMaterials():
    #controllers = [ob for ob in family(findLightGrp(context.active_object).parent) if ob.name.startswith('BLS_CONTROLLER.')]
    controllers = (ob for ob in bpy.context.scene.objects if ob.name.startswith('BLS_CONTROLLER.') and isFamily(ob))
    for cntrl in controllers:
        mat = [m for m in cntrl.data.materials if m.name.startswith('BLS_icon_ctrl')][0]
        mixNode = mat.node_tree.nodes['Mix Shader'].inputs['Fac']
        mixNode.default_value = mixNode.default_value