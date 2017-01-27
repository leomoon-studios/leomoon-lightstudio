import bpy

# original source https://github.com/dustractor/ui_teardown_recreate

def get_mergables(areas):
    xs,ys = dict(),dict()
    for a in areas:
        xs[a.x] = a
        ys[a.y] = a
    for area in reversed(areas):
        tx = area.x + area.width + 1
        ty = area.y + area.height + 1
        if tx in xs and xs[tx].y == area.y and xs[tx].height == area.height:
            return area,xs[tx]
        elif ty in ys and ys[ty].x == area.x and ys[ty].width == area.width:
            return area,ys[ty]
    return None,None

def teardown(context):
    while len(context.screen.areas) > 1:
        a,b = get_mergables(context.screen.areas)
        if a and b:
            bpy.ops.screen.area_join(min_x=a.x,min_y=a.y,max_x=b.x,max_y=b.y)
            area = context.screen.areas[0]
            region = area.regions[0]
            blend_data = context.blend_data
            bpy.ops.screen.screen_full_area(dict(screen=context.screen,window=context.window,region=region,area=area,blend_data=blend_data))
            bpy.ops.screen.back_to_previous(dict(screen=context.screen,window=context.window,region=region,area=area,blend_data=blend_data))

def area_from_ptr(ptr):
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.as_pointer() == ptr:
                return area

def split_area(window,screen,region,area,xtype,direction="VERTICAL",factor=0.5,mouse_x=-100,mouse_y=-100):
    beforeptrs = set(list((a.as_pointer() for a in screen.areas)))
    bpy.ops.screen.area_split(dict(region=region,area=area,screen=screen,window=window),direction=direction,factor=factor)
    afterptrs = set(list((a.as_pointer() for a in screen.areas)))
    newareaptr = list(afterptrs-beforeptrs)
    newarea = area_from_ptr(newareaptr[0])
    newarea.type = xtype
    return newarea


def splitV3DtoBLS(context):
    window = context.window
    region = context.region
    screen = context.screen
    main = context.area
    
    main.type = "INFO"
    
    ctrlPanel = split_area(window,screen,region,main,"VIEW_3D",direction="HORIZONTAL",factor=0.3)
    ctrlPanel.spaces[0].lock_camera_and_layers = False
    ctrlPanel.spaces[0].layers = [False]*19 + [True]
    ctrlPanel.spaces[0].show_relationship_lines
    ctrlPanel.spaces[0].viewport_shade = 'MATERIAL'
    
    override = {'window': window, 'screen': screen, 'area': ctrlPanel, 'region': ctrlPanel.regions[2], 'scene': context.scene}
    if ctrlPanel.spaces[0].region_3d.is_perspective: bpy.ops.view3d.view_persportho(override)
    bpy.ops.view3d.viewnumpad(override, type = 'TOP')
    
    #nodeEditor = split_area(window,screen,region,ctrlPanel,"NODE_EDITOR",direction="VERTICAL",factor=0.51)
    
    main.type = "VIEW_3D"
    
    
    
'''
def test_contains(bounds,point):
    ax,ay,bx,by = bounds
    x,y = point
    return (ax <= x <= bx) and (ay <= y <= by)
def example_layout(context):
    window = context.window
    region = context.region
    screen = context.screen
    main = context.screen.areas[0]
    main.type = "TEXT_EDITOR"
    info = split_area(window,screen,region,main,"INFO",direction="HORIZONTAL",factor=0.99)
    properties = split_area(window,screen,region,main,"PROPERTIES",direction="VERTICAL",factor=0.85)
    timeline = split_area(window,screen,region,main,"TIMELINE",direction="HORIZONTAL",factor=0.1)
    v3d = split_area(window,screen,region,main,"VIEW_3D",direction="VERTICAL",factor=0.7)
    lightPanel = split_area(window,screen,region,v3d,"VIEW_3D",direction="HORIZONTAL",factor=0.3)
    lightPanel.spaces[0].lock_camera_and_layers = False
    #split2 = split_area(window,screen,region,other,"NODE_EDITOR",direction="HORIZONTAL",factor=0.6)
    #split3 = split_area(window,screen,region,other,"IMAGE_EDITOR",direction="VERTICAL",factor=0.7)
    #split4 = split_area(window,screen,region,other,"VIEW_3D",direction="VERTICAL",factor=0.7)
'''
