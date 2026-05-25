"""Native bpy Camera Caddy — a PySide-free alternative to caddy.py.

Immediate-mode N-panel: selection state lives in a Scene PropertyGroup, and the
shots/cameras/planes are read from each rig armature's stored multicam_data on
every redraw. Covers the core set (lists, visibility, lens, frame jumps, opacity,
create-static). Thumbnails, move/rotate, and character-snap are deferred.
"""

from __future__ import annotations

import bpy

from magicam.blender import image_plane as mpc_ip
from magicam.blender import scene as mpc_scene

LENSES = ["16mm", "24mm", "35mm", "50mm", "85mm", "120mm", "200mm"]
_LENS_LABELS = set(LENSES)


# --- shared data access ----------------------------------------------------

def _all_shots():
    """Ordered {shot_name: camera_data} for every MagiCam rig in the scene."""
    shots = {}
    for arm in mpc_scene.get_multicam_armatures():
        data = mpc_scene.load_camera_data_from_armature(arm)
        shots[data.get("shot_name", arm.name)] = data
    return shots


def _arm_for_shot(shot_name):
    for arm in mpc_scene.get_multicam_armatures():
        data = mpc_scene.load_camera_data_from_armature(arm)
        if data.get("shot_name", arm.name) == shot_name:
            return arm
    return None


def _read_opacity(obj):
    for slot in obj.material_slots:
        mat = slot.material
        if mat and mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type == "BSDF_PRINCIPLED":
                    return node.inputs["Alpha"].default_value
    return 1.0


# --- property update callbacks ---------------------------------------------

def _on_lens_update(self, context):
    if not self.active_camera:
        return
    cam = mpc_scene.camera_object(self.active_camera)
    if cam and cam.type == "CAMERA":
        cam.data.lens = float(self.lens.replace("mm", ""))


def _on_opacity_update(self, context):
    obj = bpy.data.objects.get(self.active_plane)
    if not obj:
        return
    for slot in obj.material_slots:
        mat = slot.material
        if mat and mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type == "BSDF_PRINCIPLED":
                    node.inputs["Alpha"].default_value = self.opacity


class MagicamCaddyState(bpy.types.PropertyGroup):
    active_shot: bpy.props.StringProperty()
    active_camera: bpy.props.StringProperty()
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

class MAGICAM_OT_caddy_set_shot(bpy.types.Operator):
    bl_idname = "magicam.caddy_set_shot"
    bl_label = "Select Shot"
    shot: bpy.props.StringProperty()

    def execute(self, context):
        st = context.scene.magicam_caddy
        st.active_shot = self.shot
        st.active_camera = ""
        st.active_plane = ""
        return {"FINISHED"}


class MAGICAM_OT_caddy_set_camera(bpy.types.Operator):
    bl_idname = "magicam.caddy_set_camera"
    bl_label = "Select Camera"
    camera: bpy.props.StringProperty()

    def execute(self, context):
        st = context.scene.magicam_caddy
        st.active_camera = self.camera
        st.active_plane = ""
        cam = mpc_scene.camera_object(self.camera)
        if cam and cam.type == "CAMERA":
            label = f"{int(round(cam.data.lens))}mm"
            if label in _LENS_LABELS:
                st.lens = label
        try:
            mpc_scene.select_camera_root(self.camera.replace("Cam", "ControlRig"))
        except Exception as exc:
            print(f"[magicam] camera select skipped: {exc}")
        return {"FINISHED"}


class MAGICAM_OT_caddy_set_plane(bpy.types.Operator):
    bl_idname = "magicam.caddy_set_plane"
    bl_label = "Select Image Plane"
    plane: bpy.props.StringProperty()

    def execute(self, context):
        st = context.scene.magicam_caddy
        st.active_plane = self.plane
        obj = bpy.data.objects.get(self.plane)
        if obj:
            st.opacity = _read_opacity(obj)
            armature, bone = mpc_scene.get_image_plane_bone(obj)
            if armature and bone:
                try:
                    mpc_scene.select_image_plane(armature, bone)
                except Exception as exc:
                    print(f"[magicam] plane select skipped: {exc}")
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
    bl_description = "Set the timeline preview range to the shot's start/end"

    def execute(self, context):
        st = context.scene.magicam_caddy
        data = _all_shots().get(st.active_shot)
        if not data:
            return {"CANCELLED"}
        scene = context.scene
        scene.use_preview_range = True
        scene.frame_preview_start = int(data.get("start_frame", scene.frame_start))
        scene.frame_preview_end = int(data.get("end_frame", scene.frame_end))
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

        arm = _arm_for_shot(st.active_shot)
        if arm:
            data = mpc_scene.load_camera_data_from_armature(arm)
            cam = data.get("cameras", {}).get(st.active_camera)
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
    bl_label = "Camera Caddy (native)"
    bl_idname = "MAGICAM_PT_caddy"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MagiCam"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        st = context.scene.magicam_caddy
        shots = _all_shots()
        if not shots:
            layout.label(text="No MagiCam rigs in scene.", icon="INFO")
            return

        col = layout.column(align=True)
        col.label(text="Shots")
        for shot in shots:
            op = col.operator(
                "magicam.caddy_set_shot", text=shot, depress=(shot == st.active_shot)
            )
            op.shot = shot

        if st.active_shot not in shots:
            return
        data = shots[st.active_shot]

        row = layout.row(align=True)
        start = data.get("start_frame", "-")
        end = data.get("end_frame", "-")
        op = row.operator("magicam.caddy_jump_frame", text=f"Start {start}")
        op.frame = int(start) if str(start).lstrip("-").isdigit() else 0
        op = row.operator("magicam.caddy_jump_frame", text=f"End {end}")
        op.frame = int(end) if str(end).lstrip("-").isdigit() else 0
        row.operator("magicam.caddy_view_range", text="View Range")

        cams = data.get("cameras", {})
        col = layout.column(align=True)
        col.label(text="Cameras")
        for cam in cams:
            op = col.operator(
                "magicam.caddy_set_camera",
                text=cam,
                depress=(cam == st.active_camera),
            )
            op.camera = cam

        if st.active_camera not in cams:
            return

        layout.prop(st, "lens", text="Lens")

        planes = cams[st.active_camera].get("camera_planes", {})
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
    MAGICAM_OT_caddy_set_shot,
    MAGICAM_OT_caddy_set_camera,
    MAGICAM_OT_caddy_set_plane,
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
