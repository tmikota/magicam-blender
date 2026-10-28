"""Camera-rig appending and namespacing.

Ported PySide-free from the original multiplaneCamera create.py / alc edit.py.
Relies on the bundled rig template's collection ("magicCam") and its bone-name
conventions (MagiCam camera, image_plane_01..10 / *_ctrl bones, utils, etc.).
"""

from __future__ import annotations

import os
import re

import bpy


def addon_resources_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "resources").replace("\\", "/")


def default_rig_template_path() -> str:
    """Path to the rig template bundled with the add-on."""
    return os.path.join(
        addon_resources_dir(), "camera_rig_multiplane_simple2.blend"
    ).replace("\\", "/")


def append_camera_rig(
    blend_file, source_collection_name, dest_collection_name=None, link_into_scene=True
):
    """Append a collection from a .blend, optionally rename it, and link to scene."""
    with bpy.data.libraries.load(blend_file, link=False) as (data_from, data_to):
        if source_collection_name in data_from.collections:
            data_to.collections = [source_collection_name]
        else:
            raise ValueError(
                f"Collection '{source_collection_name}' not found in {blend_file}"
            )

    appended_collection = data_to.collections[0]

    if dest_collection_name and dest_collection_name != appended_collection.name:
        appended_collection.name = dest_collection_name

    if link_into_scene:
        if appended_collection.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(appended_collection)

    return appended_collection


# --- variable plane count --------------------------------------------------

BUNDLED_PLANES = 10  # planes (and control bones) the bundled template ships with
MAX_PLANES = 24  # hard cap; a clip with more layers is an error, not a silent skip
PLANE_SPACING = 2.0  # rig units between neighbouring template planes


def plane_count(prefix):
    """How many ``<prefix>image_plane_NN`` mesh planes exist right now."""
    pat = re.compile(rf"^{re.escape(prefix)}image_plane_\d+$")
    return sum(1 for o in bpy.data.objects if o.type == "MESH" and pat.match(o.name))


def _copy_rna(src, dst, skip=()):
    for prop in src.bl_rna.properties:
        if prop.is_readonly or prop.identifier in skip:
            continue
        try:
            setattr(dst, prop.identifier, getattr(src, prop.identifier))
        except (AttributeError, TypeError):
            pass


def _clone_control_bone(armature_obj, src_name, new_name, y_offset):
    """Add bone *new_name* *y_offset* further back than *src_name*, with the same parent, display,
    bone collections and location limit (whose floor moves with it)."""
    view_layer = bpy.context.view_layer
    prev_active = view_layer.objects.active
    view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        eb = armature_obj.data.edit_bones
        src = eb[src_name]
        new = eb.new(new_name)
        # the template's 01-09 orientation: head toward the camera, tail at the plane
        head_y, tail_y = sorted((src.head.y, src.tail.y))
        new.head = (src.head.x, head_y + y_offset, src.head.z)
        new.tail = (src.tail.x, tail_y + y_offset, src.tail.z)
        new.roll = src.roll
        new.parent = src.parent
        new.use_connect = False
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
        view_layer.objects.active = prev_active

    src_pb = armature_obj.pose.bones[src_name]
    pb = armature_obj.pose.bones[new_name]
    pb.rotation_mode = src_pb.rotation_mode
    pb.custom_shape = src_pb.custom_shape
    pb.custom_shape_scale_xyz = src_pb.custom_shape_scale_xyz
    for coll in src_pb.bone.collections:
        coll.assign(pb.bone)
    for con in src_pb.constraints:
        new_con = pb.constraints.new(con.type)
        _copy_rna(con, new_con, skip=("name", "type"))
        if con.type == "LIMIT_LOCATION":
            new_con.min_y = con.min_y - y_offset  # reach the same distance from the camera


def _clone_plane(src, prefix, number, armature_obj, bone_name):
    new = src.copy()  # copies the drivers too, so it sizes itself to the camera's frustum
    new.data = src.data.copy()
    new.name = f"{prefix}image_plane_{number:02d}"
    new.data.name = new.name
    for coll in src.users_collection:
        coll.objects.link(new)
    new.location.y = src.location.y + PLANE_SPACING
    for con in new.constraints:
        if con.type == "ARMATURE":
            for t in con.targets:
                t.target = armature_obj
                t.subtarget = bone_name
    return new


def ensure_plane_count(armature_obj, prefix, count):
    """Grow the rig to *count* planes by cloning the last plane and its control bone.

    Idempotent: a rig that already has *count* planes is left alone. Raises ValueError above
    ``MAX_PLANES``.
    """
    if count > MAX_PLANES:
        raise ValueError(
            f"This clip has {count} layers but a MagiCam rig holds at most {MAX_PLANES} image "
            "planes - group or ignore layers (Rename Layers) so fewer are exported."
        )
    have = plane_count(prefix)
    if have == 0:
        raise ValueError(f"No '{prefix}image_plane_NN' planes in the rig to clone")
    for number in range(have + 1, count + 1):
        src = bpy.data.objects[f"{prefix}image_plane_{number - 1:02d}"]
        bone = f"{prefix}image_plane_{number:02d}_ctrl"
        _clone_control_bone(
            armature_obj,
            f"{prefix}image_plane_{number - 1:02d}_ctrl",
            bone,
            PLANE_SPACING,
        )
        _clone_plane(src, prefix, number, armature_obj, bone)


def hide_after_append(collection_object, prefix=""):
    """Hide the rig's '<prefix>utils' helper object after appending."""
    utils = f"{prefix}utils"
    for obj in collection_object.children_recursive:
        if utils == obj.name:
            obj.hide_viewport = True
            obj.hide_render = True


# --- namespacing -----------------------------------------------------------

def namespace_everything(collection, prefix):
    """Apply a namespace prefix to all data types within a collection."""
    namespace_collections(collection, prefix, rename_root=False)
    namespace_objects(collection, prefix)
    namespace_materials(collection, prefix)
    namespace_images(collection, prefix)
    namespace_armatures_and_bones(collection, prefix)


def namespace_collections(collection, prefix, rename_root=False):
    if rename_root and not collection.name.startswith(prefix):
        collection.name = f"{prefix}{collection.name}"
    for child in collection.children:
        namespace_collections(child, prefix, rename_root=True)


def namespace_objects(collection, prefix):
    for obj in collection.objects:
        if not obj.name.startswith(prefix):
            obj.name = f"{prefix}{obj.name}"
    for child_collection in collection.children:
        namespace_objects(child_collection, prefix)


def namespace_materials(collection, prefix):
    for obj in collection.all_objects:
        if obj.type == "MESH":
            for slot in obj.material_slots:
                mat = slot.material
                if mat and not mat.name.startswith(prefix):
                    mat.name = f"{prefix}{mat.name}"


def namespace_images(collection, prefix):
    for obj in collection.all_objects:
        if obj.type == "MESH":
            for slot in obj.material_slots:
                mat = slot.material
                if mat and mat.use_nodes:
                    for node in mat.node_tree.nodes:
                        if node.type == "TEX_IMAGE" and node.image:
                            img = node.image
                            if not img.name.startswith(prefix):
                                img.name = f"{prefix}{img.name}"


def namespace_armatures_and_bones(collection, prefix):
    for obj in collection.all_objects:
        if obj.type == "ARMATURE":
            if not obj.name.startswith(prefix):
                obj.name = f"{prefix}{obj.name}"
            for bone in obj.data.bones:
                if not bone.name.startswith(prefix):
                    bone.name = f"{prefix}{bone.name}"
            for pbone in obj.pose.bones:
                if not pbone.name.startswith(prefix):
                    pbone.name = f"{prefix}{pbone.name}"
