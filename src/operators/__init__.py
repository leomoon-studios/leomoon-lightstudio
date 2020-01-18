# class UpdateChecker:
#     def __init__(self):
#         self.updated
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