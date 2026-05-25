"""The MagiCam N-panel: import button and a per-rig image-plane list."""

from __future__ import annotations

import bpy

from magicam.blender import scene


class MAGICAM_PT_main(bpy.types.Panel):
    bl_label = "MagiCam"
    bl_idname = "MAGICAM_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MagiCam"

    def draw(self, context):
        layout = self.layout
        layout.operator("magicam.open_caddy", icon="WINDOW")
        row = layout.row(align=True)
        row.operator("magicam.import_tvpaint", text="Import (file browser)", icon="OUTLINER_OB_CAMERA")
        row.operator("magicam.open_importer", text="Import (Caddy)", icon="WINDOW")

        armatures = scene.get_multicam_armatures()
        if not armatures:
            layout.label(text="No MagiCam rigs in scene.", icon="INFO")
            return

        for arm in armatures:
            data = scene.load_camera_data_from_armature(arm)
            box = layout.box()
            box.label(text=data.get("shot_name", arm.name), icon="ARMATURE_DATA")

            cameras = data.get("cameras", {})
            for cam_name, cam_data in cameras.items():
                planes = cam_data.get("camera_planes", {})
                if not planes:
                    box.label(text="(no planes)")
                    continue
                for plane_name in planes:
                    is_hidden = scene.hidden(plane_name)
                    row = box.row(align=True)
                    icon = "HIDE_ON" if is_hidden else "HIDE_OFF"
                    op = row.operator("magicam.toggle_plane", text=plane_name, icon=icon)
                    op.plane_name = plane_name


classes = (MAGICAM_PT_main,)
