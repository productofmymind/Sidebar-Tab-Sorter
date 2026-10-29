bl_info = {
    "name": "Sidebar Tab Sorter",
    "author": "George",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "Sidebar (N) > Tab Sorter, or Preferences > Add-ons",
    "description": "Reorder the tabs shown in the N-panel sidebar",
    "category": "Interface",
}

import json

import bpy

SPACES = [
    ('VIEW_3D', "3D Viewport", ""),
    ('IMAGE_EDITOR', "Image Editor", ""),
    ('NODE_EDITOR', "Node Editor", ""),
    ('SEQUENCE_EDITOR', "Video Sequencer", ""),
    ('CLIP_EDITOR', "Movie Clip Editor", ""),
]


def _subclasses(cls):
    for c in cls.__subclasses__():
        yield c
        yield from _subclasses(c)


def _panels(space):
    found = (c for c in _subclasses(bpy.types.Panel)
             if getattr(c, "bl_space_type", None) == space
             and getattr(c, "bl_region_type", None) == 'UI')
    return list(dict.fromkeys(found))


def _idname(cls):
    return getattr(cls, "bl_idname", None) or cls.__name__


def _category(cls, by_id):
    # sub-panels inherit the tab of their parent
    while not getattr(cls, "bl_category", "") and getattr(cls, "bl_parent_id", ""):
        parent = by_id.get(cls.bl_parent_id)
        if parent is None or parent is cls:
            break
        cls = parent
    return getattr(cls, "bl_category", "")


def _default_order(space):
    # __subclasses__ is definition order and unaffected by re-registering
    panels = _panels(space)
    by_id = {_idname(p): p for p in panels}
    cats = dict.fromkeys(_category(p, by_id) for p in panels)
    cats.pop("", None)
    return list(cats)


def _prefs():
    return bpy.context.preferences.addons[__name__].preferences


def _saved(space):
    try:
        return json.loads(_prefs().order).get(space, [])
    except Exception:
        return []


def _save(space, order):
    try:
        p = _prefs()
        d = json.loads(p.order)
        d[space] = order
        p.order = json.dumps(d)
    except Exception:
        pass


def categories(space):
    cats = _default_order(space)
    saved = [c for c in _saved(space) if c in cats]
    return saved + [c for c in cats if c not in saved]


def apply_order(space, order):
    """Tabs appear in the order their first panel was registered, so
    unregister every sidebar panel and re-register sorted by tab."""
    panels = _panels(space)
    by_id = {_idname(p): p for p in panels}
    rank = {c: i for i, c in enumerate(order)}

    def key(p):
        cat = _category(p, by_id)
        return rank.get(cat, -1 if not cat else len(rank))

    done = []
    for p in panels:
        if getattr(p, "bl_parent_id", "") and p.bl_parent_id not in by_id:
            continue  # parent lives in another region; re-registering would fail
        try:
            bpy.utils.unregister_class(p)
            done.append(p)
        except RuntimeError:
            pass  # not registered (e.g. abstract mixin)
    pending = sorted(done, key=key)
    while pending:
        # a sub-panel needs its parent registered first
        ready = next((p for p in pending
                      if not getattr(p, "bl_parent_id", "")
                      or p.bl_parent_id not in {_idname(q) for q in pending}), pending[0])
        pending.remove(ready)
        try:
            bpy.utils.register_class(ready)
        except Exception as e:
            print(f"Sidebar Tab Sorter: could not re-register {ready}: {e}")
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            a.tag_redraw()


def fill_items(wm):
    wm.ts_items.clear()
    for c in categories(wm.ts_space):
        wm.ts_items.add().name = c
    wm.ts_index = min(wm.ts_index, max(len(wm.ts_items) - 1, 0))


def commit(wm):
    order = [i.name for i in wm.ts_items]
    _save(wm.ts_space, order)
    apply_order(wm.ts_space, order)


class TABSORTER_Prefs(bpy.types.AddonPreferences):
    bl_idname = __name__
    order: bpy.props.StringProperty(default="{}")

    def draw(self, context):
        draw_ui(self.layout, context)


class TABSORTER_Item(bpy.types.PropertyGroup):
    pass


class TABSORTER_UL_tabs(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.name)


class TABSORTER_OT_move(bpy.types.Operator):
    bl_idname = "tabsorter.move"
    bl_label = "Move Tab"
    step: bpy.props.IntProperty()

    def execute(self, context):
        wm = context.window_manager
        i, j = wm.ts_index, wm.ts_index + self.step
        if not 0 <= j < len(wm.ts_items):
            return {'CANCELLED'}
        wm.ts_items.move(i, j)
        wm.ts_index = j
        commit(wm)
        return {'FINISHED'}


class TABSORTER_OT_refresh(bpy.types.Operator):
    bl_idname = "tabsorter.refresh"
    bl_label = "Refresh / Re-apply"
    bl_description = "Re-read the tab list and re-apply the saved order (use after enabling other add-ons)"

    def execute(self, context):
        wm = context.window_manager
        fill_items(wm)
        commit(wm)
        return {'FINISHED'}


class TABSORTER_OT_reset(bpy.types.Operator):
    bl_idname = "tabsorter.reset"
    bl_label = "Reset"
    bl_description = "Restore the default tab order for this editor"

    def execute(self, context):
        wm = context.window_manager
        _save(wm.ts_space, [])
        apply_order(wm.ts_space, _default_order(wm.ts_space))
        fill_items(wm)
        return {'FINISHED'}


def draw_ui(layout, context):
    wm = context.window_manager
    layout.prop(wm, "ts_space", text="")
    if not wm.ts_items:
        layout.operator("tabsorter.refresh", text="Load Tabs", icon='FILE_REFRESH')
        return
    row = layout.row()
    row.template_list("TABSORTER_UL_tabs", "", wm, "ts_items", wm, "ts_index", rows=8)
    col = row.column(align=True)
    col.operator("tabsorter.move", icon='TRIA_UP', text="").step = -1
    col.operator("tabsorter.move", icon='TRIA_DOWN', text="").step = 1
    row = layout.row(align=True)
    row.operator("tabsorter.refresh", icon='FILE_REFRESH')
    row.operator("tabsorter.reset", icon='LOOP_BACK')


class TABSORTER_PT_main(bpy.types.Panel):
    bl_label = "Tab Order"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tab Sorter"

    def draw(self, context):
        draw_ui(self.layout, context)


classes = (TABSORTER_Prefs, TABSORTER_Item, TABSORTER_UL_tabs, TABSORTER_OT_move,
           TABSORTER_OT_refresh, TABSORTER_OT_reset, TABSORTER_PT_main)


def _startup():
    # runs after all other add-ons have registered their panels
    for space, _, _ in SPACES:
        order = _saved(space)
        if order:
            apply_order(space, order)
    fill_items(bpy.context.window_manager)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    wm = bpy.types.WindowManager
    wm.ts_items = bpy.props.CollectionProperty(type=TABSORTER_Item)
    wm.ts_index = bpy.props.IntProperty()
    wm.ts_space = bpy.props.EnumProperty(
        items=SPACES, name="Editor",
        update=lambda self, ctx: fill_items(self))
    bpy.app.timers.register(_startup, first_interval=1.0)


def unregister():
    if bpy.app.timers.is_registered(_startup):
        bpy.app.timers.unregister(_startup)
    wm = bpy.types.WindowManager
    del wm.ts_items, wm.ts_index, wm.ts_space
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
