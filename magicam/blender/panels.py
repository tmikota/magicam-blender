"""The top MagiCam panel: import a TVPaint camera.

Per-camera/plane management lives in the Camera Caddy panel (caddy_blender.py).
"""

from __future__ import annotations

import bpy


class MAGICAM_PT_main(bpy.types.Panel):
    bl_label = "MagiCam"
    bl_idname = "MAGICAM_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MagiCam"

    def draw(self, context):
        col = self.layout.column(align=True)
        col.operator("magicam.import_tvpaint", icon="OUTLINER_OB_CAMERA")
        col.operator("magicam.import_timeline", icon="SEQUENCE")


classes = (MAGICAM_PT_main,)
