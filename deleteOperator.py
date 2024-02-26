import bpy
from bpy.props import BoolProperty
from . common import findLightGrp, isFamily
from . import light_list
from . operators import modal
from . light_operators import _delete_leomoon_studio_light

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
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and any(ob for ob in context.selected_objects if ob.protected)

    def execute(self, context):
        protected_objects = (ob for ob in context.selected_objects if ob.protected)

        try:
            for obj in protected_objects:
                if (obj and obj.name.startswith('LLS_HANDLE')):
                    self.report({'ERROR'}, "Delete Profile in order to delete Handle")
                    return {'FINISHED'}

                if hasattr(obj, 'use_fake_user'):
                    obj.use_fake_user = False
                try:
                    _delete_leomoon_studio_light(context, obj)
                except Exception as e:
                    import traceback 
                    traceback.print_exc()
                    self.report({'WARNING', 'ERROR'}, "Error while deleting light")
                    return {'FINISHED'}
        except ReferenceError:
            return {'FINISHED'}

        
        bpy.ops.object.delete('INVOKE_DEFAULT', use_global=self.use_global, confirm=False)

        if context.scene.LLStudio.initialized:
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
        bpy.app.timers.register(register_keymaps, first_interval=0.25)
    else:
        # can now proceed with checking default kmis
        try:
            print('registering keymap')
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
        except Exception as e:
            print("Keymap registering failed. Trying again...", e)
            bpy.app.timers.register(register_keymaps, first_interval=0.25)


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