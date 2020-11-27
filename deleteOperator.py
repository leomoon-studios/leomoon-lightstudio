import bpy
from bpy.props import BoolProperty
from . common import findLightGrp, isFamily
from . import light_list
from . operators import modal

class DeleteOperator(bpy.types.Operator):
    """ Custom delete """
    bl_idname = "object.delete_custom"
    bl_label = "Custom Delete"
    bl_options = {'REGISTER', 'UNDO'}

    use_global: BoolProperty(default = False, name="Delete Globally")
    confirm: BoolProperty(default = True, name="Confirm")

    @classmethod
    def poll(cls, context):
        if not context.area:
            return True
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    def execute(self, context):
        protected_objects = (ob for ob in context.selected_objects if ob.protected)

        for obj in protected_objects:
            context.view_layer.objects.active = obj
            if hasattr(obj, 'use_fake_user'):
                obj.use_fake_user = False
            try:
                ret = bpy.ops.scene.delete_leomoon_studio_light()
            except:
                self.report({'WARNING', 'ERROR'}, "Delete Profile in order to delete Handle")
                return {'FINISHED'}
            else:
                if 'CANCELLED' in ret:
                    self.report({'WARNING', 'ERROR'}, "Delete Profile in order to delete Handle")
                    return {'FINISHED'}


        bpy.ops.object.delete('INVOKE_DEFAULT', use_global=self.use_global, confirm=False)

        light_list.update_light_list_set(context)

        return {'FINISHED'}

    def invoke(self, context, event):
        if self.confirm:
            if not modal.running_modals:
                return context.window_manager.invoke_confirm(self, event)
            if modal.running_modals and not isFamily(context.object):
                return context.window_manager.invoke_confirm(self, event)
        return self.execute(context)



def register_keymaps():
    kc = bpy.context.window_manager.keyconfigs
    areas = 'Window', 'Text', 'Object Mode', '3D View'

    if not all(i in kc.active.keymaps for i in areas):
        bpy.app.timers.register(register_keymaps, first_interval=0.1)
    else:
        # can now proceed with checking default kmis
        km, kmis =  get_user_keymap_item('Object Mode', 'object.delete', multiple_entries=True)
        wm = bpy.context.window_manager
        addon_km = wm.keyconfigs.addon.keymaps.new(name='Object Mode', space_type='EMPTY')
        for default_kmi in kmis:
            addon_kmi = addon_km.keymap_items.new(DeleteOperator.bl_idname, default_kmi.type, default_kmi.value)
            addon_kmi.map_type = default_kmi.map_type
            if hasattr(addon_kmi, 'repeat'):
                addon_kmi.repeat = default_kmi.repeat
            addon_kmi.any = default_kmi.any
            addon_kmi.shift = default_kmi.shift
            addon_kmi.ctrl = default_kmi.ctrl
            addon_kmi.alt = default_kmi.alt
            addon_kmi.oskey = default_kmi.oskey
            addon_kmi.key_modifier = default_kmi.key_modifier
            addon_kmi.properties.use_global = default_kmi.properties.use_global
            addon_kmi.properties.confirm = default_kmi.properties.confirm

            addon_keymaps.append((addon_km, addon_kmi))


from . common import get_user_keymap_item
addon_keymaps = []
def add_shortkeys():
    # overcome load-addons-before-keyconfigs issue
    register_keymaps()

def remove_shortkeys():
    wm = bpy.context.window_manager
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)

    addon_keymaps.clear()