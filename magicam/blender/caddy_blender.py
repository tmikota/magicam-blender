"""Native bpy Camera Caddy — the Blender UI for MagiCam rigs (no PySide).

Immediate-mode N-panel: selection state lives in a Scene PropertyGroup, and the
cameras/planes are read from each rig armature's stored multicam_data on every
redraw. One shot == one camera, so cameras are listed directly (no shot list) as
a dropdown. Clicking a plane selects its rig control bone.
Deferred: thumbnail strip, move/rotate, character-snap.
"""

from __future__ import annotations

import bpy

from magicam.blender import image_plane as mpc_ip
from magicam.blender import scene as mpc_scene

LENSES = ["16mm", "24mm", "35mm", "50mm", "85mm", "120mm", "200mm"]
_LENS_LABELS = set(LENSES)

# Camera rig control bones: (suffix after the rig prefix, label, transform tool).
# Translate controls activate the Move tool; tilt activates Rotate.
CONTROL_BONES = [
    ("main", "Base", "builtin.move"),
    ("dolly", "Dolly", "builtin.move"),
    ("height", "Height", "builtin.move"),
    ("tilt", "Tilt", "builtin.rotate"),
]

# Keep a reference to the dynamic enum items so Blender doesn't GC the strings.
_camera_enum_items = []


# --- shared data access ----------------------------------------------------

def _all_cameras():
    """{camera_name: (shot, armature, camera_dict, start, end)} across all rigs."""
    cameras = {}
    for arm in mpc_scene.get_multicam_armatures():
        data = mpc_scene.load_camera_data_from_armature(arm)
        shot = data.get("shot_name", arm.name)
        start = data.get("start_frame", 0)
        end = data.get("end_frame", 0)
        for cam_name, cam_dict in data.get("cameras", {}).items():
            cameras[cam_name] = (shot, arm, cam_dict, start, end)
    return cameras




def _to_int(value, fallback=0):
    return int(value) if str(value).lstrip("-").isdigit() else fallback


# --- dynamic enum / update callbacks ---------------------------------------

def _camera_items(self, context):
    global _camera_enum_items
    names = list(_all_cameras().keys())
    _camera_enum_items = [(n, n, "") for n in names] or [("", "(no cameras)", "")]
    return _camera_enum_items


def _on_camera_update(self, context):
    self.active_plane = ""
    if not self.camera:
        return
    cam = mpc_scene.camera_object(self.camera)
    if cam and cam.type == "CAMERA":
        label = f"{int(round(cam.data.lens))}mm"
        if label in _LENS_LABELS:
            self.lens = label
    try:
        mpc_scene.select_camera_root(self.camera.replace("Cam", "ControlRig"))
    except Exception as exc:
        print(f"[magicam] camera select skipped: {exc}")


def _on_lens_update(self, context):
    if not self.camera:
        return
    cam = mpc_scene.camera_object(self.camera)
    if cam and cam.type == "CAMERA":
        cam.data.lens = float(self.lens.replace("mm", ""))


def _on_opacity_update(self, context):
    obj = bpy.data.objects.get(self.active_plane)
    if obj:
        mpc_ip.set_plane_opacity(obj, self.opacity)


class MagicamCaddyState(bpy.types.PropertyGroup):
    camera: bpy.props.EnumProperty(
        name="Camera", items=_camera_items, update=_on_camera_update
    )
    active_plane: bpy.props.StringProperty()
    lens: bpy.props.EnumProperty(
        name="Lens",
        items=[(label, label, "") for label in LENSES],
        default="50mm",
        update=_on_lens_update,
    )
    opacity: bpy.props.FloatProperty(
        name="Opacity", min=0.0, max=1.0, default=1.0, update=_on_opacity_update
    )


# --- operators -------------------------------------------------------------

class MAGICAM_OT_caddy_set_plane(bpy.types.Operator):
    bl_idname = "magicam.caddy_set_plane"
    bl_label = "Select Image Plane"
    bl_description = "Select this plane and its rig control bone"
    plane: bpy.props.StringProperty()

    def execute(self, context):
        st = context.scene.magicam_caddy
        st.active_plane = self.plane
        obj = bpy.data.objects.get(self.plane)
        if obj:
            st.opacity = mpc_ip.get_plane_opacity(obj)
            armature, bone = mpc_scene.get_image_plane_bone(obj)
            if armature and bone:
                try:
                    mpc_scene.select_image_plane(armature, bone)
                except Exception as exc:
                    print(f"[magicam] plane control select skipped: {exc}")
        return {"FINISHED"}


class MAGICAM_OT_caddy_select_control(bpy.types.Operator):
    bl_idname = "magicam.caddy_select_control"
    bl_label = "Select Camera Control"
    bl_description = "Select this control bone on the active camera's rig (grab with G)"
    bone: bpy.props.StringProperty()
    tool: bpy.props.StringProperty(default="builtin.move")

    def execute(self, context):
        st = context.scene.magicam_caddy
        entry = _all_cameras().get(st.camera)
        if not entry:
            return {"CANCELLED"}
        arm = entry[1]
        mpc_scene.select_bone_on_rig(arm, self.bone)
        # Switch to the matching transform tool so non-Blender users can just drag.
        try:
            bpy.ops.wm.tool_set_by_id(name=self.tool)
        except Exception as exc:
            print(f"[magicam] could not set tool '{self.tool}': {exc}")
        return {"FINISHED"}


class MAGICAM_OT_caddy_jump_frame(bpy.types.Operator):
    bl_idname = "magicam.caddy_jump_frame"
    bl_label = "Jump To Frame"
    frame: bpy.props.IntProperty()

    def execute(self, context):
        mpc_scene.set_current_frame(self.frame)
        return {"FINISHED"}


class MAGICAM_OT_caddy_view_range(bpy.types.Operator):
    bl_idname = "magicam.caddy_view_range"
    bl_label = "View Range"
    bl_description = "Set the timeline preview range to this camera's shot range"

    def execute(self, context):
        st = context.scene.magicam_caddy
        entry = _all_cameras().get(st.camera)
        if not entry:
            return {"CANCELLED"}
        _, _, _, start, end = entry
        scene = context.scene
        scene.use_preview_range = True
        scene.frame_preview_start = _to_int(start, scene.frame_start)
        scene.frame_preview_end = _to_int(end, scene.frame_end)
        return {"FINISHED"}


class MAGICAM_OT_caddy_create_static(bpy.types.Operator):
    bl_idname = "magicam.caddy_create_static"
    bl_label = "Create Static"
    bl_description = "Duplicate the active plane as a static plane at the current frame"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = context.scene.magicam_caddy
        if not st.active_plane:
            return {"CANCELLED"}
        obj = mpc_scene.get_image_plane_object(st.active_plane)
        if not obj:
            self.report({"WARNING"}, f"Plane '{st.active_plane}' not found.")
            return {"CANCELLED"}
        new_obj = mpc_ip.static_image_plane(obj)

        entry = _all_cameras().get(st.camera)
        if entry:
            _, arm, _, _, _ = entry
            data = mpc_scene.load_camera_data_from_armature(arm)
            cam = data.get("cameras", {}).get(st.camera)
            if cam is not None:
                frames = (
                    cam["camera_planes"].get(st.active_plane, {}).get("image_frames", [])
                )
                cam["camera_planes"][new_obj.name] = {
                    "enabled": True,
                    "static_created": True,
                    "image_frames": frames,
                }
                mpc_scene.store_camera_data_on_armature(arm, data)
        self.report({"INFO"}, f"Created static plane '{new_obj.name}'")
        return {"FINISHED"}


# --- panel -----------------------------------------------------------------

class MAGICAM_PT_caddy(bpy.types.Panel):
    bl_label = "Camera Caddy"
    bl_idname = "MAGICAM_PT_caddy"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MagiCam"

    def draw(self, context):
        layout = self.layout
        st = context.scene.magicam_caddy
        cameras = _all_cameras()
        if not cameras:
            layout.label(text="No MagiCam rigs in scene.", icon="INFO")
            return

        layout.prop(st, "camera", text="Camera")
        if st.camera not in cameras:
            return
        _, arm, cam_dict, start, end = cameras[st.camera]

        row = layout.row(align=True)
        op = row.operator("magicam.caddy_jump_frame", text=f"Start {start}")
        op.frame = _to_int(start)
        op = row.operator("magicam.caddy_jump_frame", text=f"End {end}")
        op.frame = _to_int(end)
        row.operator("magicam.caddy_view_range", text="View Range")

        # Camera controls: select a rig control bone (ready to grab).
        prefix = st.camera.rsplit("MagiCam", 1)[0]
        controls = [
            (suffix, label, tool)
            for suffix, label, tool in CONTROL_BONES
            if arm and arm.pose.bones.get(f"{prefix}{suffix}")
        ]
        if controls:
            col = layout.column(align=True)
            col.label(text="Camera Controls")
            crow = col.row(align=True)
            for suffix, label, tool in controls:
                op = crow.operator("magicam.caddy_select_control", text=label)
                op.bone = f"{prefix}{suffix}"
                op.tool = tool

        layout.prop(st, "lens", text="Lens")

        planes = cam_dict.get("camera_planes", {})
        col = layout.column(align=True)
        col.label(text="Image Planes")
        for plane in planes:
            prow = col.row(align=True)
            is_hidden = mpc_scene.hidden(plane)
            tog = prow.operator(
                "magicam.toggle_plane",
                text="",
                icon="HIDE_ON" if is_hidden else "HIDE_OFF",
            )
            tog.plane_name = plane
            sel = prow.operator(
                "magicam.caddy_set_plane",
                text=plane,
                depress=(plane == st.active_plane),
            )
            sel.plane = plane

        if st.active_plane in planes:
            box = layout.box()
            box.prop(st, "opacity", slider=True)
            box.operator("magicam.caddy_create_static", icon="IMAGE_DATA")


_classes = (
    MagicamCaddyState,
    MAGICAM_OT_caddy_set_plane,
    MAGICAM_OT_caddy_select_control,
    MAGICAM_OT_caddy_jump_frame,
    MAGICAM_OT_caddy_view_range,
    MAGICAM_OT_caddy_create_static,
    MAGICAM_PT_caddy,
)


def register():
    for cls in _classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)
    bpy.types.Scene.magicam_caddy = bpy.props.PointerProperty(type=MagicamCaddyState)


def unregister():
    if hasattr(bpy.types.Scene, "magicam_caddy"):
        del bpy.types.Scene.magicam_caddy
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
