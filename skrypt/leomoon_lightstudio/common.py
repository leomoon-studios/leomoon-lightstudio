import bpy

def replace_link(object, collection_name):
    if isinstance(object, bpy.types.Collection):
        bpy.context.scene.collection.children.unlink(bpy.context.scene.collection.children[object.name])
        bpy.data.collections[collection_name].children.link(object)
    else:
        object.users_collection[0].objects.unlink(object)
        bpy.data.collections[collection_name].objects.link(object)

def get_collection(object):
    return [c for c in object.users_collection if c.name.startswith('BLS')][0]

def get_bls_collection(context):
    return [c for c in context.scene.collection.children if c.name.startswith('BLS')][0]

def blscol_profilecol_profile_handle(context):
    bls_collection = [c for c in context.scene.collection.children if c.name.startswith('BLS')][0]
    profile_collection = [c for c in bls_collection.children if c.name.startswith('BLS_PROFILE')][0]
    profile = [ob for ob in profile_collection.objects if ob.name.startswith('BLS_PROFILE')][0]
    handle = [ob for ob in profile.children if ob.name.startswith('BLS_HANDLE')][0]
    return bls_collection, profile_collection, profile, handle

def blscol_profilecol(context):
    bls_collection = [c for c in context.scene.collection.children if c.name.startswith('BLS')][0]
    profile_collection = [c for c in bls_collection.children if c.name.startswith('BLS_PROFILE')][0]
    return bls_collection, profile_collection

def find_view_layer(collection, layer_collection):
    idx = layer_collection.children.find(collection.name)
    if idx >= 0:
        return layer_collection.children[idx]
    else:
        for vc in layer_collection.children:
            rcol = find_view_layer(collection, layer_collection=vc)
            if rcol:
                return rcol
            
def get_view_layers(layer_collection):
    for lc in layer_collection.children:
        yield lc
        for clc in get_view_layers(layer_collection=lc):
            yield clc
            
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
    while ob and ob.parent:
        ob = ob.parent
        if ob.name.startswith('BLS_LIGHT.'): return ob
    return None

def getLightMesh():
    #obs = bpy.context.scene.objects
    #lightGrp = obs.active
    #light_no = lightGrp.name.split('.')[1]
    #return obs[obs.find('BLS_LIGHT_MESH.'+light_no)]

    lg = findLightGrp(bpy.context.active_object)
    lm = [l for l in family(lg) if l.name.startswith("BLS_LIGHT_MESH")]
    return lm[0] if len(lm) else None

def getLightController():
    obs = bpy.context.view_layer.objects
    lightGrp = obs.active
    light_no = lightGrp.name.split('.')[1]
    return obs[obs.find('BLS_CONTROLLER.'+light_no)]


def findLightProfile(ob):
    if ob.name.startswith('BLS_PROFILE'):
        return ob
    
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

def refreshMaterials():
    #controllers = [ob for ob in family(findLightGrp(context.active_object).parent) if ob.name.startswith('BLS_CONTROLLER.')]
    controllers = (ob for ob in bpy.context.scene.objects if ob.name.startswith('BLS_CONTROLLER.') and isFamily(ob))
    for cntrl in controllers:
        mat = [m for m in cntrl.data.materials if m.name.startswith('BLS_icon_ctrl')][0]
        mixNode = mat.node_tree.nodes['Mix Shader'].inputs['Fac']
        mixNode.default_value = mixNode.default_value