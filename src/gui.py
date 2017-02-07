import bpy
import os
from . common import getLightMesh

class BLS_Studio(bpy.types.Panel):
    bl_idname = "bls_studio"
    bl_label = "Studio"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Light Studio"
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'    
    
    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        if not context.scene.BLStudio.initialized: col.operator('scene.create_blender_light_studio')
        if context.scene.BLStudio.initialized: col.operator('scene.delete_blender_light_studio')
        col.operator('scene.prepare_blender_studio_light')

class BLS_ProfileList(bpy.types.Panel):
    bl_idname = "bls_profile_list"
    bl_label = "Profiles"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Light Studio"
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and context.scene.BLStudio.initialized
            
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        props = scene.BLStudio
        
        row = layout.row()
        col = row.column()
        col.template_list("BLS_UL_List", "Profile_List", props, "profile_list", props, "list_index", rows=5)
        
        col = row.column(align=True)
        col.operator('bls_list.new_profile', icon='ZOOMIN', text="")
        col.operator('bls_list.delete_profile', icon='ZOOMOUT', text="")
        col.operator('bls_list.copy_profile', icon='GHOST', text="")
        
        col.separator()
        col.operator('bls_list.move_profile', text='', icon="TRIA_UP").direction = 'UP'
        col.operator('bls_list.move_profile', text='', icon="TRIA_DOWN").direction = 'DOWN'
                
class BLS_Lights(bpy.types.Panel):
    bl_idname = "bls_lights"
    bl_label = "Lights"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Light Studio"
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and len(context.scene.BLStudio.profile_list)
    
    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator('scene.add_blender_studio_light', text='Add Light')
        row.operator('scene.delete_blender_studio_light', text='Delete Light')
        
class BLS_Selected(bpy.types.Panel):
    bl_idname = "bls_selected"
    bl_label = "Selected Light"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Light Studio"
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'    
    
    def draw(self, context):
        if context.scene.objects.active and (context.scene.objects.active.name.startswith('BLS_CONTROLLER') or context.scene.objects.active.name.startswith('BLS_LIGHT_MESH')):
            layout = self.layout
            wm = context.window_manager
            
            col = layout.column(align=True)
            col.operator('bls.light_brush', text="3D Edit", icon='CURSOR')
            
            box = layout.box()
            col = box.column()
            col.template_icon_view(wm, "bls_tex_previews", show_labels=True)
            col.label(os.path.splitext(wm.bls_tex_previews)[0])
            
            col = layout.column(align=True)
            col.prop(context.scene.BLStudio, 'light_muted')
            
            
            layout.separator()
            try:
                bls_inputs = getLightMesh().active_material.node_tree.nodes["Group"].inputs
                for input in bls_inputs[1:]:
                    if input.type == "RGBA":
                        layout.prop(input, 'default_value', input.name)
                        col = layout.column(align=True)
                    else:
                        col.prop(input, 'default_value', input.name)
            except:
                col.label("BLS_light material is not valid.")
            col.prop(context.scene.BLStudio, 'light_radius')
                
class BLS_Visibility(bpy.types.Panel):
    bl_idname = "bls_visibility"
    bl_label = "Visibility Options"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Light Studio"
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and len(context.scene.BLStudio.profile_list)
    
    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator('object.mute_other_lights')
        col.operator('object.show_all_lights')
        
class BLS_ProfileImportExport(bpy.types.Panel):
    bl_idname = "bls_profile_import_export"
    bl_label = "Import/Export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Light Studio"
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and context.scene.BLStudio.initialized
            
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        props = scene.BLStudio
              
        col = layout.column(align=True)
        col.operator('bls.export_profiles', text="Export Selected Profile")
        col.operator('bls.export_profiles', text="Export All Profiles").all=True
        col.operator('bls.import_profiles')