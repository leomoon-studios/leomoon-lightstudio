UPDATED = True

def is_updated():
    global UPDATED
    return UPDATED

def update():
    global UPDATED
    UPDATED = True

def update_clear():
    global UPDATED
    UPDATED = False

VERBOSE = True

AREA_DEFAULT_SIZE = 9

from .. common import isFamily
class LightOperator:
    @classmethod
    def poll(cls, context):
        object = context.active_object
        return context.area.type == 'VIEW_3D' and \
               context.mode == 'OBJECT' and \
               context.space_data.type == 'VIEW_3D' and \
               context.scene.LLStudio.initialized and \
               object and \
               object.name.startswith('LLS_LIGHT_') and \
               isFamily(object) and \
               object.select_get()