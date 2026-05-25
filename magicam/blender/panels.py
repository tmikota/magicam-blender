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
        self.layout.operator("magicam.import_tvpaint", icon="OUTLINER_OB_CAMERA")


classes = (MAGICAM_PT_main,)
