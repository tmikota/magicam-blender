"""Operators: import a TVPaint camera, and toggle an image plane's visibility."""

from __future__ import annotations

import bpy
from bpy_extras.io_utils import ImportHelper

from magicam.blender import build, prefs, scene


class MAGICAM_OT_import_tvpaint(bpy.types.Operator, ImportHelper):
    bl_idname = "magicam.import_tvpaint"
    bl_label = "Import TVPaint Camera"
    bl_description = "Build a multiplane camera rig from a TVPaint clip_export.json"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    shot_name: bpy.props.StringProperty(
        name="Shot Name",
        description=(
            "Prefix/namespace for the rig. Leave blank to use the TVPaint clip "
            "name, uppercased (e.g. CLIP_139)."
        ),
        default="",
    )
    shot_start_frame: bpy.props.IntProperty(
        name="Shot Start Frame",
        description="Timeline frame the shot starts on (0 = derive from layers)",
        default=0,
        min=0,
    )

    def execute(self, context):
        start = self.shot_start_frame or None
        result = build.import_multicam_rig(
            self.filepath,
            shot_name=self.shot_name or None,
            shot_start_frame=start,
            enable_pipeline=prefs.get_enable_pipeline(),
        )
        if result is None:
            self.report({"WARNING"}, "Nothing imported (see console).")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Imported rig '{result.name}'")
        return {"FINISHED"}


def _launch(which):
    """Import caddy lazily so the add-on registers even without PySide6."""
    try:
        from magicam.blender import caddy
    except ImportError as exc:
        return f"PySide6 not available in Blender's Python: {exc}"
    fn = getattr(caddy, which)
    result = fn()
    if result is None and which == "launch_caddy":
        return "No MagiCam rigs in the scene to manage."
    return None


class MAGICAM_OT_open_caddy(bpy.types.Operator):
    bl_idname = "magicam.open_caddy"
    bl_label = "Open Camera Caddy"
    bl_description = "Open the PySide6 Camera Caddy for the rigs in this scene"

    def execute(self, context):
        err = _launch("launch_caddy")
        if err:
            self.report({"WARNING"}, err)
            return {"CANCELLED"}
        return {"FINISHED"}


class MAGICAM_OT_open_importer(bpy.types.Operator):
    bl_idname = "magicam.open_importer"
    bl_label = "Camera Importer (Caddy)"
    bl_description = "Open the PySide6 TVPaint camera importer dialog"

    def execute(self, context):
        err = _launch("launch_camera_importer")
        if err:
            self.report({"WARNING"}, err)
            return {"CANCELLED"}
        return {"FINISHED"}


class MAGICAM_OT_toggle_plane(bpy.types.Operator):
    bl_idname = "magicam.toggle_plane"
    bl_label = "Toggle Image Plane"
    bl_description = "Show/hide an image plane"
    bl_options = {"REGISTER", "UNDO"}

    plane_name: bpy.props.StringProperty()

    def execute(self, context):
        result = scene.toggle_image_plane(self.plane_name)
        if result is None:
            self.report({"WARNING"}, f"Plane '{self.plane_name}' not found.")
            return {"CANCELLED"}
        return {"FINISHED"}


classes = (
    MAGICAM_OT_import_tvpaint,
    MAGICAM_OT_open_caddy,
    MAGICAM_OT_open_importer,
    MAGICAM_OT_toggle_plane,
)
