"""Scene-level queries and edits for MagiCam rigs.

Ported PySide-free from the original multiplaneCamera query.py/edit.py/create.py
and alc edit.py/create.py.
"""

from __future__ import annotations

import json
import re

import bpy

CGL_TYPE_RIG = "mpc_rig"


# --- queries ---------------------------------------------------------------

def get_viewport_camera():
    """The camera currently used in the active 3D viewport, if any."""
    for area in bpy.context.window.screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    if space.region_3d.view_perspective == "CAMERA":
                        return space.camera
    return None


def multiplane_cams():
    """Objects tagged cgl_type == 'mpc_rig'."""
    return [obj for obj in bpy.data.objects if obj.get("cgl_type") == CGL_TYPE_RIG]


def get_multicam_armatures():
    """Armatures carrying stored 'multicam_data'."""
    return [
        obj
        for obj in bpy.data.objects
        if obj.type == "ARMATURE" and "multicam_data" in obj
    ]


def armature_object(rig_collection):
    """Recursively find the armature within a collection (name or Collection)."""
    if isinstance(rig_collection, str):
        rig_collection = bpy.data.collections.get(rig_collection)
        if not rig_collection:
            return None
    for obj in rig_collection.objects:
        if obj.type == "ARMATURE":
            return obj
    for child in rig_collection.children:
        found = armature_object(child)
        if found:
            return found
    return None


def camera_object(camera_name, collection_name=None):
    """Recursively find a camera by (sub)name, optionally within a collection."""

    def recursive_search(collection):
        for obj in collection.objects:
            if obj.type == "CAMERA" and camera_name in obj.name:
                return obj
        for child in collection.children:
            result = recursive_search(child)
            if result:
                return result
        return None

    if collection_name:
        collection = bpy.data.collections.get(collection_name)
        return recursive_search(collection) if collection else None
    for obj in bpy.data.objects:
        if obj.type == "CAMERA" and camera_name in obj.name:
            return obj
    return None


def get_image_plane_object(name):
    obj = bpy.data.objects.get(name)
    return obj if obj and obj.type == "MESH" else None


def hidden(name):
    """Viewport-hidden state of a mesh object (None if not found)."""
    obj = bpy.data.objects.get(name)
    if obj and obj.type == "MESH":
        return obj.hide_viewport
    return None


# --- camera data on armature ----------------------------------------------

def store_camera_data_on_armature(armature, camera_data: dict):
    armature["multicam_data"] = json.dumps(camera_data)


def load_camera_data_from_armature(armature) -> dict:
    if "multicam_data" in armature:
        return json.loads(armature["multicam_data"])
    return {}


# --- visibility ------------------------------------------------------------

def key_visibility(obj_name, frame, visible=True):
    obj = bpy.data.objects.get(obj_name)
    if not obj:
        print(f"Object '{obj_name}' not found.")
        return
    obj.hide_viewport = not visible
    obj.hide_render = not visible
    obj.keyframe_insert(data_path="hide_viewport", frame=frame)
    obj.keyframe_insert(data_path="hide_render", frame=frame)


def toggle_image_plane(name):
    """Flip a mesh plane's visibility; returns the new visible state, or None."""
    obj = bpy.data.objects.get(name)
    if obj and obj.type == "MESH":
        now_visible = obj.hide_viewport  # True means currently hidden
        obj.hide_viewport = not now_visible
        obj.hide_render = not now_visible
        obj.hide_set(not now_visible)
        return now_visible
    print(f"Object '{name}' not found or not a mesh.")
    return None


def hide_image_planes_without_material(prefix):
    """Hide leftover rig planes ('<prefix>image_plane_NN') that got no material."""
    plane_prefix = f"{prefix}image_plane_"
    for obj in bpy.data.objects:
        if obj.name.startswith(plane_prefix) and obj.type == "MESH":
            has_material = any(slot.material for slot in obj.material_slots)
            obj.hide_viewport = not has_material
            obj.hide_render = not has_material


def toggle_image_plane_controls(prefix, control_prefix="image_plane_"):
    """Hide control bones for rig planes that did not receive an image/material."""
    control_prefix = f"{prefix}{control_prefix}"
    rig = next(
        (
            obj
            for obj in bpy.data.objects
            if obj.type == "ARMATURE"
            and any(bone.name.startswith(control_prefix) for bone in obj.pose.bones)
        ),
        None,
    )
    if not rig:
        return

    for i in range(1, 11):
        plane_name = f"{control_prefix}{i:02d}"
        ctrl_name = f"{plane_name}_ctrl"
        plane_obj = bpy.data.objects.get(plane_name)
        pose_bone = rig.pose.bones.get(ctrl_name)
        if not plane_obj or not pose_bone:
            continue
        has_material = any(
            slot.material and slot.material.node_tree
            for slot in plane_obj.material_slots
        )
        pose_bone.bone.hide = not has_material


# --- collections / frame range / markers -----------------------------------

def ensure_collection(name):
    """Return the named collection, creating and linking it to the scene if needed."""
    coll = bpy.data.collections.get(name)
    if not coll:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def move_collection_to_collection(child_collection, parent_collection):
    """Reparent a collection under another in the outliner (names or objects)."""
    child = (
        bpy.data.collections.get(child_collection)
        if isinstance(child_collection, str)
        else child_collection
    )
    parent = (
        bpy.data.collections.get(parent_collection)
        if isinstance(parent_collection, str)
        else parent_collection
    )
    if not child or not parent or child == parent:
        return

    if child.name in bpy.context.scene.collection.children.keys():
        bpy.context.scene.collection.children.unlink(child)
    for coll in bpy.data.collections:
        if coll != parent and child.name in coll.children.keys():
            coll.children.unlink(child)
    if child.name not in parent.children.keys():
        parent.children.link(child)


def set_frame_range(start, end, current=None):
    bpy.context.scene.frame_start = int(start)
    bpy.context.scene.frame_end = int(end)
    if current is not None:
        bpy.context.scene.frame_current = int(current)


def timeline_mark(marker_name, frame=None, camera_obj=None):
    marker = bpy.context.scene.timeline_markers.new(name="temp", frame=frame)
    if camera_obj:
        marker.camera = camera_obj
    marker.name = marker_name
    bpy.context.scene.camera = None


def _camera_marker_switcher(scene):
    frame = scene.frame_current
    applicable = [m for m in scene.timeline_markers if m.camera and m.frame <= frame]
    if applicable:
        scene.camera = sorted(applicable, key=lambda m: m.frame)[-1].camera


def enable_multicam_playback():
    if _camera_marker_switcher not in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.append(_camera_marker_switcher)


def disable_multicam_playback():
    if _camera_marker_switcher in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.remove(_camera_marker_switcher)


def set_current_frame(frame_number):
    bpy.context.scene.frame_current = int(frame_number)


# --- rig / bone selection (used by the Camera Caddy) -----------------------

def select_rig_root(rig_name, root_bone_name):
    """Select a rig and its root bone, entering Pose mode. Self-contained."""
    rig = bpy.data.objects.get(rig_name)
    if not rig or rig.type != "ARMATURE":
        print(f"Rig '{rig_name}' not found or not an armature.")
        return
    if rig.library or rig.override_library:
        print(f"Rig '{rig_name}' is linked/overridden; cannot select.")
        return
    try:
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    if rig.mode != "POSE":
        try:
            bpy.ops.object.mode_set(mode="POSE")
        except RuntimeError as exc:
            print(f"Could not enter Pose mode: {exc}")
            return
    _deselect_all_pose_bones(rig)
    pbone = rig.pose.bones.get(root_bone_name)
    if pbone:
        _set_bone_selected(pbone, True)
        try:
            rig.data.bones.active = pbone.bone
        except Exception as exc:
            print(f"Could not set active bone: {exc}")
    else:
        print(f"Bone '{root_bone_name}' not found on '{rig_name}'.")


def _set_bone_selected(pose_bone, state):
    """Set a bone's select state, tolerating API moves across Blender versions.

    Blender 5.x dropped ``Bone.select``; try the PoseBone and the underlying
    Bone, setting whichever still exposes ``select``.
    """
    for target in (pose_bone, pose_bone.bone):
        if hasattr(target, "select"):
            try:
                target.select = state
                return True
            except Exception:
                pass
    return False


def _deselect_all_pose_bones(rig_object):
    try:
        bpy.ops.pose.select_all(action="DESELECT")
        return
    except Exception:
        pass
    for pb in rig_object.pose.bones:
        _set_bone_selected(pb, False)


def select_bone_on_rig(rig_object, bone_name):
    """Select and activate a single pose bone by name on the given armature."""
    if isinstance(rig_object, str):
        rig_object = bpy.data.objects.get(rig_object)
    if not rig_object or rig_object.type != "ARMATURE":
        print("Provided object is not an armature.")
        return
    try:
        bpy.context.view_layer.objects.active = rig_object
        rig_object.select_set(True)
        if rig_object.mode != "POSE":
            bpy.ops.object.mode_set(mode="POSE")
    except RuntimeError as exc:
        print(f"Failed to switch to Pose mode: {exc}")

    pbone = rig_object.pose.bones.get(bone_name)
    if not pbone:
        print(f"Bone '{bone_name}' not found on '{rig_object.name}'.")
        return

    _deselect_all_pose_bones(rig_object)
    _set_bone_selected(pbone, True)
    try:
        rig_object.data.bones.active = pbone.bone
    except Exception as exc:
        print(f"Could not set active bone: {exc}")


def select_camera_root(camera_rig_name):
    root_bone_name = camera_rig_name.replace("MagiControlRig", "main")
    select_rig_root(camera_rig_name, root_bone_name)


def select_image_plane(rig_object, image_plane_control_name):
    select_bone_on_rig(rig_object, image_plane_control_name)


def select_character_rig(character_rig_name):
    select_rig_root(character_rig_name, "c_pose")


def get_character_rig_c_pose(name_fragment):
    """Find the 'c_pos' pose bone of an armature in a collection matching the fragment."""
    for collection in bpy.data.collections:
        if name_fragment.lower() in collection.name.lower():
            for obj in collection.all_objects:
                if obj.type == "ARMATURE":
                    return obj.pose.bones.get("c_pos")
            return None
    return None


def get_image_plane_bone(image_plane_object):
    """Return (armature_object, bone_name) of the control bone driving a plane.

    Tries the common rig bindings in order: Armature constraint, Child-Of
    constraint, bone parenting, then an Armature modifier matched to a vertex
    group whose name is a bone. Returns (None, None) if nothing matches.
    """
    if isinstance(image_plane_object, str):
        image_plane_object = bpy.data.objects.get(image_plane_object)
    if not image_plane_object:
        return None, None

    # 1) Armature (bone) constraint with a bone target.
    for c in image_plane_object.constraints:
        if c.type == "ARMATURE" and c.targets:
            t = c.targets[0]
            if t and t.target and t.subtarget:
                return t.target, t.subtarget

    # 2) Child Of constraint pointing at a bone.
    for c in image_plane_object.constraints:
        if c.type == "CHILD_OF" and c.target and getattr(c, "subtarget", ""):
            return c.target, c.subtarget

    # 3) Bone parenting.
    if (
        image_plane_object.parent
        and image_plane_object.parent.type == "ARMATURE"
        and image_plane_object.parent_type == "BONE"
        and image_plane_object.parent_bone
    ):
        return image_plane_object.parent, image_plane_object.parent_bone

    # 4) Armature modifier + a vertex group that names a bone.
    arm = next(
        (m.object for m in image_plane_object.modifiers
         if m.type == "ARMATURE" and m.object),
        None,
    )
    if arm:
        bone_names = {b.name for b in arm.data.bones}
        for vg in image_plane_object.vertex_groups:
            if vg.name in bone_names:
                return arm, vg.name

    # 5) Fallback: the rig's stored data owns this plane. Use an explicit
    # control_bone if recorded at import, else rebuild it from the plane's
    # 'ipNN' material token and the stored prefix (image_plane_NN_ctrl).
    plane_num = None
    for slot in image_plane_object.material_slots:
        mat = slot.material
        match = re.search(r"ip(\d+)", mat.name) if mat else None
        if match:
            plane_num = match.group(1).zfill(2)
            break
    for arm in get_multicam_armatures():
        data = load_camera_data_from_armature(arm)
        prefix = data.get("prefix", "")
        for cam in data.get("cameras", {}).values():
            entry = cam.get("camera_planes", {}).get(image_plane_object.name)
            if entry is None:
                continue
            bone = entry.get("control_bone")
            if bone and arm.pose.bones.get(bone):
                return arm, bone
            if plane_num:
                bone = f"{prefix}image_plane_{plane_num}_ctrl"
                if arm.pose.bones.get(bone):
                    return arm, bone

    return None, None
