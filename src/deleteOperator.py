import bpy
from bpy.props import BoolProperty
from . common import findLightGrp

class DeleteOperator(bpy.types.Operator):
    """ Custom delete """
    bl_idname = "object.delete_custom" 
    bl_label = "Custom Delete"
    bl_options = {'REGISTER', 'UNDO'}

    use_global = BoolProperty(default = False)

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'
    
    def execute(self, context):
        protected_groups = [findLightGrp(ob) for ob in context.selected_objects if ob.protected]
        protected_objects = (ob for ob in context.selected_objects if ob.protected)
        
        for obj in protected_objects:
            context.scene.objects.active = obj
            if hasattr(obj, 'use_fake_user'):
                obj.use_fake_user = False
            bpy.ops.scene.delete_blender_studio_light()
        
        bpy.ops.object.delete(use_global=self.use_global)

        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_confirm(self, event)
        
addon_keymaps = []
def add_shortkeys():       
    wm = bpy.context.window_manager
    addon_km = wm.keyconfigs.addon.keymaps.new(name='Object Mode', space_type='EMPTY')
    
    addon_kmi = addon_km.keymap_items.new(DeleteOperator.bl_idname, 'X', 'PRESS')
    addon_kmi.properties.use_global = False
    
    addon_kmi = addon_km.keymap_items.new(DeleteOperator.bl_idname, 'X', 'PRESS')
    addon_kmi.shift = True
    addon_kmi.properties.use_global = True
    
    addon_kmi = addon_km.keymap_items.new(DeleteOperator.bl_idname, 'DEL', 'PRESS')
    addon_kmi.properties.use_global = False
    
    addon_kmi = addon_km.keymap_items.new(DeleteOperator.bl_idname, 'DEL', 'PRESS')
    addon_kmi.shift = True
    addon_kmi.properties.use_global = True
    
    addon_keymaps.append(addon_km)

def remove_shortkeys():
    wm = bpy.context.window_manager
    for km in addon_keymaps:
        wm.keyconfigs.addon.keymaps.remove(km)
        
    addon_keymaps.clear()
