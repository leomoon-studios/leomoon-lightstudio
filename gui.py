import bpy
import os
from . common import getLightMesh
from . auto_load import force_register
from . import operators
import traceback

@force_register
class LLS_PT_Studio(bpy.types.Panel):
    bl_idname = "LLS_PT_studio"
    bl_label = "Studio"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "LightStudio"

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        if not context.scene.LLStudio.initialized: col.operator('scene.create_leomoon_light_studio')
        if context.scene.LLStudio.initialized: col.operator('scene.delete_leomoon_light_studio')
        col.separator()
        col.operator('light_studio.control_panel', icon='MENU_PANEL')
        col.operator('scene.switch_to_cycles')
        col.operator('scene.set_light_studio_background')

@force_register
class LLS_PT_Mode(bpy.types.Panel):
    bl_idname = "LLS_PT_mode"
    bl_label = "Mode"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "LightStudio"

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and context.scene.LLStudio.initialized

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        props = scene.LLStudio

        row = layout.row(align=True)
        row.prop(props, 'lls_mode', expand=True)

@force_register
class LLS_PT_ProfileList(bpy.types.Panel):
    bl_idname = "LLS_PT_profile_list"
    bl_label = "Profiles"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "LightStudio"

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and context.scene.LLStudio.initialized

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        props = scene.LLStudio

        row = layout.row()
        col = row.column()
        col.prop(props, 'profile_multimode', expand=True)
        col.template_list("LLS_UL_ProfileList", "Profile_List", props, "profile_list", props, "profile_list_index", rows=5)

        col = row.column(align=True)
        col.operator('lls_list.new_profile', icon='ADD', text="")
        col.operator('lls_list.delete_profile', icon='REMOVE', text="")
        col.operator('lls_list.copy_profile_menu', icon='DUPLICATE', text="")

        col.separator()
        col.operator('lls_list.move_profile', text='', icon="TRIA_UP").direction = 'UP'
        col.operator('lls_list.move_profile', text='', icon="TRIA_DOWN").direction = 'DOWN'

@force_register
class LLS_PT_Lights(bpy.types.Panel):
    bl_idname = "LLS_PT_lights"
    bl_label = "Lights"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "LightStudio"

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and len(context.scene.LLStudio.profile_list)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)

        props = context.scene.LLStudio

        row = layout.row()
        col = row.column()
        if props.profile_multimode:
            col.label(text="Profile: "+props.profile_list[props.profile_list_index].name)
        col.template_list("LLS_UL_LightList", "Light_List", props, "light_list", props, "light_list_index", rows=5)

        col = row.column(align=True)
        col.operator('scene.add_leomoon_studio_light', icon='ADD', text="")
        col.operator('scene.delete_leomoon_studio_light', icon='REMOVE', text="").confirm=False
        col.operator('lls_list.copy_light', icon='DUPLICATE', text="")

        col.separator()
        col.operator('lls_list.move_light', text='', icon="TRIA_UP").direction = 'UP'
        col.operator('lls_list.move_light', text='', icon="TRIA_DOWN").direction = 'DOWN'


@force_register
class LLS_PT_Selected(bpy.types.Panel):
    bl_idname = "LLS_PT_selected"
    bl_label = "Selected Light"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "LightStudio"

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and context.scene.LLStudio.initialized
        # return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    def draw(self, context):
        if context.active_object and context.active_object.name.startswith('LLS_LIGHT_'):
            layout = self.layout
            wm = context.window_manager

            col = layout.column(align=True)
            # col.operator('lls.light_brush', text="3D Edit", icon='PIVOT_CURSOR')

            row = col.row()
            # row.prop(context.scene.LLStudio, 'active_light_type', expand=True)
            row.prop(context.object.parent.LLStudio, 'type', expand=True)
            col.separator()

            if context.object.type == 'LIGHT':
                row = col.row()
                row.prop(context.object.data.LLStudio, 'color')
                col.prop(context.object.data.LLStudio, 'color_saturation', slider=True)
                col.prop(context.object.data.LLStudio, 'intensity')
            elif context.object.type == 'MESH':
                box = layout.box()
                col = box.column()
                col.template_icon_view(wm, "lls_tex_previews", show_labels=True)
                col.label(text=os.path.splitext(wm.lls_tex_previews)[0])

                layout.separator()
                try:
                    lls_inputs = getLightMesh().active_material.node_tree.nodes["Group"].inputs
                    for input in lls_inputs[2:]:
                        if input.type == "RGBA":
                            layout.prop(input, 'default_value', text=input.name)
                            col = layout.column(align=True)
                        else:
                            col.prop(input, 'default_value', text=input.name)
                except:
                    col.label(text="LLS_light material is not valid.")
                    if operators.VERBOSE:
                        traceback.print_exc()
            col.prop(getLightMesh().parent, 'location', index=2, text="Distance") #light radius

@force_register
class LLS_PT_ProfileImportExport(bpy.types.Panel):
    bl_idname = "LLS_PT_profile_import_export"
    bl_label = "Import/Export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "LightStudio"

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and context.scene.LLStudio.initialized

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        box = layout.box()
        box.label(text="Animation export not supported.", icon='ERROR')

        col = layout.column(align=True)
        col.operator('lls_list.export_profiles', text="Export Selected Profile")
        col.operator('lls_list.export_profiles', text="Export All Profiles").all=True
        col.operator('lls_list.import_profiles', text="Import Profiles")

from . import bl_info
@force_register
class LLS_PT_Misc(bpy.types.Panel):
    bl_idname = "LLS_PT_misc"
    bl_label = "Misc"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "LightStudio"

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' #and context.scene.LLStudio.initialized

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.operator('lls.find_missing_textures')
        col.operator('lls.open_textures_folder')
        col.operator('light_studio.reset_control_panel')
        col.operator('lls.lls_keyingset')
        if context.scene.keying_sets.active and context.scene.keying_sets.active.bl_idname == "BUILTIN_KSI_LightStudio":
            box = layout.box()
            box.label(text="Keying Set is active.", icon='CHECKMARK')

class LLSKeyingSet(bpy.types.Operator):
    bl_idname = "lls.lls_keyingset"
    bl_description = "Activate LightStudio Keying Set to animate lights"
    bl_label = "LightStudio Keying Set"
    bl_options = {"INTERNAL", "UNDO"}
    @classmethod
    def poll(self, context):
        """ Enable if there's something in the list """
        return len(context.scene.LLStudio.profile_list)

    def execute(self, context):
        context.scene.keying_sets.active = [k for k in context.scene.keying_sets_all if k.bl_idname == "BUILTIN_KSI_LightStudio"][0]
        return {"FINISHED"}

@force_register
class LLS_PT_Hotkeys(bpy.types.Panel):
    bl_idname = "LLS_PT_hotkeys"
    bl_label = "Hotkeys"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "LightStudio"
    #bl_options = {'DEFAULT_CLOSED'}

    #@classmethod
    #def poll(cls, context):
    #    return context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' #and context.scene.LLStudio.initialized

    scale_kmi_type = 'X'
    rotate_kmi_type = 'X'


    def draw(self, context):
        layout = self.layout
        scene = context.scene

        props = scene.LLStudio

        box = layout.box()

        box.label(text="Move light", icon='MOUSE_LMB')
        row = box.row(align=True)

        row.label(text="Scale light", icon=self.__class__.scale_kmi_type)
        row = box.row(align=True)

        row.label(text="Rotate light", icon=self.__class__.rotate_kmi_type)
        row = box.row(align=True)

        row.label(text="Precision mode", icon='EVENT_SHIFT')
        row = box.row(align=True)

        box.label(text="Mute light", icon='MOUSE_LMB_DRAG')

        box.label(text="Isolate light", icon='MOUSE_RMB')
        row = box.row(align=True)

        row.label(text="", icon='EVENT_CTRL')
        row.label(text="Loop overlapping lights", icon='MOUSE_LMB')
        row = box.row(align=True)

        box.label(text="(numpad) Icon scale up", icon='ADD')

        box.label(text="(numpad) Icon scale down", icon='REMOVE')


import rna_keymap_ui
from . common import get_user_keymap_item
from . import light_brush, deleteOperator
from . operators import modal
class LLSPreferences(bpy.types.AddonPreferences):
    # this must match the addon name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = __package__

    def draw(self, context):
        layout = self.layout

        col = layout.column()
        kc = bpy.context.window_manager.keyconfigs.user
        keymap_modified = False
        for km, kmi in light_brush.addon_keymaps + modal.addon_keymaps:
            km = km.active()
            col.context_pointer_set("keymap", km)
            user_km, user_kmi = get_user_keymap_item(km.name, kmi.idname)
            if user_kmi:
                rna_keymap_ui.draw_kmi(["ADDON", "USER", "DEFAULT"], kc, user_km, user_kmi, col, 0)
            else:
                keymap_modified = True
        if keymap_modified:
            col.operator("preferences.keymap_restore", text="Restore")

        col.separator()
        box = layout.box()
        box.label(text="Internal object.delete operator wrappers to handle deleting of Light Studio objects.")
        box.label(text="Wrapper operators copy their counterparts's settings during addon start.")
        user_keymap_items = set()
        for km, kmi in deleteOperator.addon_keymaps:
            km = km.active()
            box.context_pointer_set("keymap", km)
            user_km, user_kmis = get_user_keymap_item(km.name, kmi.idname, multiple_entries=True)
            new_set = set(user_kmis) - user_keymap_items
            for new_item in new_set:
                rna_keymap_ui.draw_kmi(["ADDON", "USER", "DEFAULT"], kc, user_km, new_item, box, 0)
            user_keymap_items |= new_set

def register():
    import functools
    def read_keymaps(counter):
        if counter == 0:
            print("Keymaps not read.")
            return

        try:
            km, kmi = get_user_keymap_item('Object Mode', 'light_studio.scale')
            LLS_PT_Hotkeys.scale_kmi_type = f'EVENT_{kmi.type}'
            km, kmi = get_user_keymap_item('Object Mode', 'light_studio.rotate')
            LLS_PT_Hotkeys.rotate_kmi_type = f'EVENT_{kmi.type}'
        except Exception:
            if operators.VERBOSE:
                traceback.print_exc()
            bpy.app.timers.register(functools.partial(read_keymaps, counter-1), first_interval=0.1)

    bpy.app.timers.register(functools.partial(read_keymaps, 10), first_interval=0.1)