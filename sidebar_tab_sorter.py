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


PROTECTED = "Tab Sorter"  # never hideable, or you couldn't get back
_hidden_panels = set()  # panels we unregistered to hide their tab


def _prefs():
    return bpy.context.preferences.addons[__name__].preferences


def _load(key, space):
    try:
        return json.loads(getattr(_prefs(), key)).get(space, [])
    except Exception:
        return []


def _store(key, space, value):
    try:
        p = _prefs()
        d = json.loads(getattr(p, key))
        d[space] = value
        setattr(p, key, json.dumps(d))
    except Exception:
        pass


def categories(space):
    cats = _default_order(space)
    saved = [c for c in _load("order", space) if c in cats]
    return saved + [c for c in cats if c not in saved]


def apply_order(space, order, hidden=()):
    """Tabs appear in the order their first panel was registered, so
    unregister every sidebar panel and re-register sorted by tab.
    Panels of hidden tabs are left unregistered."""
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
        if p in _hidden_panels:
            done.append(p)  # already unregistered by us
            continue
        try:
            bpy.utils.unregister_class(p)
            done.append(p)
        except RuntimeError:
            pass  # not registered (e.g. abstract mixin)
    pending = []
    for p in sorted(done, key=key):
        if _category(p, by_id) in hidden:
            _hidden_panels.add(p)
        else:
            _hidden_panels.discard(p)
            pending.append(p)
    while pending:
        # a sub-panel needs its parent registered first
        ids = {_idname(q) for q in pending}
        ready = next((p for p in pending
                      if not getattr(p, "bl_parent_id", "")
                      or p.bl_parent_id not in ids), pending[0])
        pending.remove(ready)
        try:
            bpy.utils.register_class(ready)
        except Exception as e:
            print(f"Sidebar Tab Sorter: could not re-register {ready}: {e}")
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            a.tag_redraw()


def commit(space, order=None):
    order = order or categories(space)
    _store("order", space, order)
    apply_order(space, order, _load("hidden", space))


class TABSORTER_Prefs(bpy.types.AddonPreferences):
    bl_idname = __name__
    order: bpy.props.StringProperty(default="{}")
    hidden: bpy.props.StringProperty(default="{}")

    def draw(self, context):
        draw_ui(self.layout, context)


class TABSORTER_OT_move(bpy.types.Operator):
    bl_idname = "tabsorter.move"
    bl_label = "Move Tab"
    bl_description = "Move this tab up/down"
    name: bpy.props.StringProperty()
    step: bpy.props.IntProperty()

    def execute(self, context):
        space = context.window_manager.ts_space
        order = categories(space)
        i = order.index(self.name)
        j = i + self.step
        if not 0 <= j < len(order):
            return {'CANCELLED'}
        order.insert(j, order.pop(i))
        commit(space, order)
        return {'FINISHED'}


class TABSORTER_OT_hide(bpy.types.Operator):
    bl_idname = "tabsorter.hide"
    bl_label = "Show/Hide Tab"
    bl_description = "Show or hide this tab"
    name: bpy.props.StringProperty()

    def execute(self, context):
        space = context.window_manager.ts_space
        hidden = _load("hidden", space)
        if self.name in hidden:
            hidden.remove(self.name)
        elif self.name != PROTECTED:
            hidden.append(self.name)
        _store("hidden", space, hidden)
        commit(space)
        return {'FINISHED'}


class TABSORTER_OT_reset(bpy.types.Operator):
    bl_idname = "tabsorter.reset"
    bl_label = "Reset"
    bl_description = "Restore default order and show all tabs for this editor"

    def execute(self, context):
        space = context.window_manager.ts_space
        _store("order", space, [])
        _store("hidden", space, [])
        apply_order(space, _default_order(space))
        return {'FINISHED'}


class TABSORTER_OT_refresh(bpy.types.Operator):
    bl_idname = "tabsorter.refresh"
    bl_label = "Re-apply"
    bl_description = "Re-apply the saved order (use after enabling other add-ons)"

    def execute(self, context):
        commit(context.window_manager.ts_space)
        return {'FINISHED'}


def draw_ui(layout, context):
    wm = context.window_manager
    space = wm.ts_space
    layout.prop(wm, "ts_space", text="")
    hidden = _load("hidden", space)
    col = layout.column(align=True)
    for name in categories(space):
        row = col.row(align=True)
        off = name in hidden
        row.label(text=name)
        eye = row.row(align=True)
        eye.enabled = name != PROTECTED
        eye.operator("tabsorter.hide", text="", icon='HIDE_ON' if off else 'HIDE_OFF',
                     depress=off).name = name
        for icon, step in (('TRIA_UP', -1), ('TRIA_DOWN', 1)):
            op = row.operator("tabsorter.move", icon=icon, text="")
            op.name, op.step = name, step
    row = layout.row(align=True)
    row.operator("tabsorter.refresh", icon='FILE_REFRESH')
    row.operator("tabsorter.reset", icon='LOOP_BACK')


class TABSORTER_PT_main(bpy.types.Panel):
    bl_label = "Tab Order"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = PROTECTED

    def draw(self, context):
        draw_ui(self.layout, context)


classes = (TABSORTER_Prefs, TABSORTER_OT_move, TABSORTER_OT_hide,
           TABSORTER_OT_reset, TABSORTER_OT_refresh, TABSORTER_PT_main)


def _startup():
    # runs after all other add-ons have registered their panels
    for space, _, _ in SPACES:
        if _load("order", space) or _load("hidden", space):
            commit(space)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.ts_space = bpy.props.EnumProperty(items=SPACES, name="Editor")
    bpy.app.timers.register(_startup, first_interval=1.0)


def unregister():
    if bpy.app.timers.is_registered(_startup):
        bpy.app.timers.unregister(_startup)
    for space, _, _ in SPACES:  # bring hidden tabs back
        apply_order(space, _default_order(space))
    del bpy.types.WindowManager.ts_space
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
