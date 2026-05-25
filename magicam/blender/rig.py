"""Camera-rig appending and namespacing.

Ported PySide-free from the original multiplaneCamera create.py / alc edit.py.
Relies on the bundled rig template's collection ("magicCam") and its bone-name
conventions (MagiCam camera, image_plane_01..10 / *_ctrl bones, utils, etc.).
"""

from __future__ import annotations

import os

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
