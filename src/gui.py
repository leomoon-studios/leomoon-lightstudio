import bpy
import os
from . common import getLightMesh
from . auto_load import force_register

@force_register
class BLS_PT_Studio(bpy.types.Panel):
    bl_idname = "BLS_PT_studio"
    bl_label = "Studio"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Light Studio"
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'    
    
    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        if not context.scene.BLStudio.initialized: col.operator('scene.create_blender_light_studio')
        if context.scene.BLStudio.initialized: col.operator('scene.delete_blender_light_studio')
        col.separator()
        col.operator('light_studio.control_panel', icon='MENU_PANEL')

@force_register
class BLS_PT_Lights(bpy.types.Panel):
    bl_idname = "BLS_PT_lights"
    bl_label = "Lights"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
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

@force_register
class BLS_PT_Selected(bpy.types.Panel):
    bl_idname = "BLS_PT_selected"
    bl_label = "Selected Light"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Light Studio"
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'
    
    def draw(self, context):
        if context.active_object and (context.active_object.name.startswith('BLS_CONTROLLER') or context.active_object.name.startswith('BLS_LIGHT_MESH')):
            layout = self.layout
            wm = context.window_manager
            
            col = layout.column(align=True)
            col.operator('bls.light_brush', text="3D Edit", icon='PIVOT_CURSOR')
            
            box = layout.box()
            col = box.column()
            col.template_icon_view(wm, "bls_tex_previews", show_labels=True)
            col.label(text=os.path.splitext(wm.bls_tex_previews)[0])
            
            layout.separator()
            try:
                bls_inputs = getLightMesh().active_material.node_tree.nodes["Group"].inputs
                for input in bls_inputs[2:]:
                    if input.type == "RGBA":
                        layout.prop(input, 'default_value', text=input.name)
                        col = layout.column(align=True)
                    else:
                        col.prop(input, 'default_value', text=input.name)
            except:
                col.label(text="BLS_light material is not valid.")
                #import traceback
                #traceback.print_exc()
            col.prop(getLightMesh(), 'location', index=0) #light radius

@force_register
class BLS_PT_ProfileList(bpy.types.Panel):
    bl_idname = "BLS_PT_profile_list"
    bl_label = "Profiles"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
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
        col.operator('bls_list.new_profile', icon='PLUS', text="")
        col.operator('bls_list.delete_profile', icon='TRASH', text="")
        col.operator('bls_list.copy_profile_menu', icon='DUPLICATE', text="")
        
        col.separator()
        col.operator('bls_list.move_profile', text='', icon="TRIA_UP").direction = 'UP'
        col.operator('bls_list.move_profile', text='', icon="TRIA_DOWN").direction = 'DOWN'

@force_register
class BLS_PT_ProfileImportExport(bpy.types.Panel):
    bl_idname = "BLS_PT_profile_import_export"
    bl_label = "Import/Export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Light Studio"
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and context.scene.BLStudio.initialized
            
    def draw(self, context):
        layout = self.layout
        scene = context.scene
              
        col = layout.column(align=True)
        col.operator('bls_list.export_profiles', text="Export Selected Profile")
        col.operator('bls_list.export_profiles', text="Export All Profiles").all=True
        col.operator('bls_list.import_profiles')

from . import bl_info
@force_register
class BLS_PT_Misc(bpy.types.Panel):
    bl_idname = "BLS_PT_misc"
    bl_label = "Misc"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Light Studio"
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' #and context.scene.BLStudio.initialized
                
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        props = scene.BLStudio
              
        col = layout.column(align=True)
        col.operator('bls.find_missing_textures')
        col.operator('bls.bls_keyingset')
        if context.scene.keying_sets.active and context.scene.keying_sets.active.bl_idname == "BUILTIN_KSI_LightStudio":
            box = col.box()
            box.label(text="Keying Set is active")

class BLSKeyingSet(bpy.types.Operator):
    """Activate Light Studio Keying Set to animate lights"""
    bl_idname = "bls.bls_keyingset"
    bl_description = "Activate Light Studio Keying Set to animate lights"
    bl_label = "Light Studio Keying Set"
    bl_options = {"INTERNAL", "UNDO"}

    def execute(self, context):
        context.scene.keying_sets.active = [k for k in context.scene.keying_sets_all if k.bl_idname == "BUILTIN_KSI_LightStudio"][0]
        return {"FINISHED"}