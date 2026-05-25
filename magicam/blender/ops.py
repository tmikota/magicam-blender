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


classes = (MAGICAM_OT_import_tvpaint, MAGICAM_OT_toggle_plane)
