# dmgbuild settings for the public macOS installer DMG.
#
# Values that depend on the current build are passed via `-D` defines from
# scripts/build_macos.py so this file can stay static and reviewable.

app_bundle = defines["app_bundle"]  # noqa: F821
background_image = defines["background_image"]  # noqa: F821
volume_icon = defines.get("volume_icon")  # noqa: F821
app_name = defines.get("app_name", "MotionSmith")  # noqa: F821
app_bundle_name = f"{app_name}.app"

format = "UDZO"
filesystem = "HFS+"
compression_level = 9

icon = volume_icon
background = background_image

show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False

window_rect = ((200, 120), (520, 340))
default_view = "icon-view"
include_icon_view_settings = "auto"
show_icon_preview = False
arrange_by = None
grid_offset = (0, 0)
grid_spacing = 100
scroll_position = (0, 0)

icon_size = 96
text_size = 14
label_pos = "bottom"

files = [(app_bundle, app_bundle_name)]
symlinks = {"Applications": "/Applications"}
hide_extensions = [app_bundle_name]
hide = [".background.tiff"]

icon_locations = {
    app_bundle_name: (145, 220),
    "Applications": (375, 220),
}
