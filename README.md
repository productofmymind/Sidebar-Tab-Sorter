# Sidebar Tab Sorter

Blender add-on to reorder the tabs in the N-panel sidebar (Tool, View, Animation, Edit, …).

Blender orders tabs by registration order, so you normally can't change it. This add-on re-registers sidebar panels sorted by your chosen tab order.

## Install

1. Download `sidebar_tab_sorter.py`.
2. Blender → Edit → Preferences → Add-ons → Install… (4.2+: top-right dropdown → *Install from Disk*) → pick the file → enable it.

## Use

Press **N** in the 3D viewport → **Tab Sorter** tab. Pick the editor, select a tab in the list, use the up/down arrows. The sidebar updates live. The same UI is in the add-on's preferences.

- **Refresh** — re-read tabs and re-apply the order (after enabling other add-ons).
- **Reset** — back to default order.
- Order is saved in add-on preferences and re-applied on startup (needs preference auto-save on, the default).
- Supports 3D Viewport, Image, Node, Sequencer and Clip editors.

## Limitations

- Tabs made only of C-coded panels (e.g. the 3D viewport *Item* tab) can't be listed or moved.
- Add-ons enabled later register their tabs at the end; hit Refresh.

