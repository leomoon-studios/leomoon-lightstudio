import bpy

def context_show_popup(context, text, title, icon):
    context.window_manager.popup_menu(lambda s, c: s.layout.label(text=text), title=title, icon=icon)

def get_user_keymap_item(keymap_name, keymap_item_idname, multiple_entries=False):
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.user

    km = kc.keymaps.get(keymap_name)
    if multiple_entries:
        return km, [i[1] for i in km.keymap_items.items() if i[0] == keymap_item_idname]
    else:
        return km, km.keymap_items.get(keymap_item_idname)

def replace_link(object, collection_name):
    if isinstance(object, bpy.types.Collection):
        bpy.context.scene.collection.children.unlink(bpy.context.scene.collection.children[object.name])
        bpy.data.collections[collection_name].children.link(object)
    else:
        object.users_collection[0].objects.unlink(object)
        bpy.data.collections[collection_name].objects.link(object)

def get_collection(object):
    return [c for c in object.users_collection if c.name.startswith('LLS')][0]

def get_lls_collection(context):
    return [c for c in context.scene.collection.children if c.name.startswith('LLS')][0]

def llscol_profilecol_profile_handle(context):
    props = context.scene.LLStudio
    profile_empty_name = props.profile_list[props.profile_list_index].empty_name
    lls_collection = [c for c in context.scene.collection.children if c.name.startswith('LLS')][0]
    # profile_collection = [c for c in lls_collection.children if c.name == profile_empty_name][0]
    profile_collection = get_collection(bpy.data.objects[profile_empty_name])
    profile = [ob for ob in profile_collection.objects if ob.name.startswith('LLS_PROFILE')][0]
    handle = [ob for ob in profile.children if ob.name.startswith('LLS_HANDLE')][0]
    return lls_collection, profile_collection, profile, handle

def llscol_profilecol(context):
    try:
        props = context.scene.LLStudio
        lls_collection = [c for c in context.scene.collection.children if c.name.startswith('LLS')][0]
        # profile_collection = [c for c in lls_collection.children if c.name.startswith('LLS_PROFILE')][0]
        profile_empty_name = props.profile_list[props.profile_list_index].empty_name
        profile_collection = get_collection(bpy.data.objects[profile_empty_name])
        return lls_collection, profile_collection
    except IndexError:
        return (None, None)

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
        ob = bpy.context.view_layer.objects.active
        if not ob:
            return False

    if ob.name.startswith('LEOMOON_LIGHT_STUDIO'): return True
    if not ob.name.startswith('LLS_'): return False
    while ob.parent:
        ob = ob.parent
        if ob.name.startswith('LEOMOON_LIGHT_STUDIO'): return True

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
        if ob.name.startswith('LLS_LIGHT.'): return ob
    return None

def findLightProfileObject(ob):
    if ob.name.startswith('LLS_PROFILE'):
        return ob

    while ob and ob.parent:
        ob = ob.parent
        if ob.name.startswith('LLS_PROFILE.'): return ob
    return None

def getLightMesh():
    lg = findLightGrp(bpy.context.active_object)
    lm = [l for l in family(lg) if l.name.startswith("LLS_LIGHT_MESH")]
    return lm[0] if len(lm) else None

def getProfileHandle(ob=None):
    if not ob:
        ob = bpy.context.scene.objects.active

    p = findLightProfileObject(ob)
    if not p:
        return None

    h = [h for h in p.children if h.name.startswith('LLS_HANDLE')]
    if len(h):
        return h[0]
    else:
        return None

def duplicate_collection(collection, parent_collection):
    new_names = {}
    matrix_data = {}
    profile_handle = [obj for obj in collection.objects if obj.name.startswith("LLS_HANDLE")]
    profile_handle = profile_handle[0] if profile_handle else None
    print(profile_handle)

    def rec_dup(collection, parent_collection):
        new_collection = bpy.data.collections.new(collection.name)
        new_collection.use_fake_user = True
        for obj in collection.objects:
            new_obj = obj.copy()

            new_names[obj.name] = new_obj
            matrix_data[new_obj.name] = {
                "matrix_basis": obj.matrix_basis.copy(),
                "matrix_local": obj.matrix_local.copy(),
                "matrix_parent_inverse": obj.matrix_parent_inverse.copy(),
                "matrix_world": obj.matrix_world.copy()
                }

            if new_obj.data:
                new_obj.data = obj.data.copy()
            for slot in new_obj.material_slots:
                slot.material = slot.material.copy()
            new_obj.parent = obj.parent
            new_collection.objects.link(new_obj)

        for obj in new_collection.objects:
            if obj.parent:
                if obj.parent.name in new_names:
                    obj.parent = new_names[obj.parent.name]
                obj.matrix_basis = matrix_data[obj.name]["matrix_basis"]
                #obj.matrix_local = matrix_data[obj.name]["matrix_local"]
                obj.matrix_parent_inverse = matrix_data[obj.name]["matrix_parent_inverse"]
                #obj.matrix_world = matrix_data[obj.name]["matrix_world"]
                if profile_handle and obj.name.startswith("LLS_LIGHT_HANDLE"):
                    obj.constraints['Child Of'].target = new_names[profile_handle.name]
                    obj.constraints['Child Of'].inverse_matrix.identity()

        if parent_collection:
            parent_collection.children.link(new_collection)

        iter_list = collection.children[:]
        parent_collection = new_collection

        for col in iter_list:
            rec_dup(col, parent_collection)

        return parent_collection

    return rec_dup(collection, parent_collection)