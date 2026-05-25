"""Image-plane material setup and image-sequence keyframing.

Ported PySide-free from the cglumberjack image_plane tool and the original
multiplaneCamera create.py.
"""

from __future__ import annotations

import os
import re

import bpy


def _set_transparent_material(mat):
    """Configure alpha-blended transparency across Blender 4.0-4.1 and 4.2+ (EEVEE Next).

    4.0/4.1 use Material.blend_method/shadow_method; 4.2+ replaced those with
    surface_render_method and use_transparent_shadow.
    """
    if hasattr(mat, "blend_method"):
        mat.blend_method = "BLEND"
    elif hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"

    if hasattr(mat, "shadow_method"):
        mat.shadow_method = "CLIP"
    elif hasattr(mat, "use_transparent_shadow"):
        mat.use_transparent_shadow = True

    if hasattr(mat, "use_backface_culling"):
        mat.use_backface_culling = False


def get_frame_numbers(image_path):
    """Sorted frame numbers of every "name.####.ext" file beside image_path."""
    folder = os.path.dirname(image_path)
    filename = os.path.basename(image_path)

    match = re.match(r"(.+)\.(\d{4})\.(\w+)$", filename)
    if not match:
        raise ValueError("Filename does not match expected pattern: name.####.ext")

    base, _, ext = match.groups()
    pattern = re.compile(rf"{re.escape(base)}\.(\d{{4}})\.{re.escape(ext)}")
    return sorted(
        int(pattern.match(f).group(1)) for f in os.listdir(folder) if pattern.match(f)
    )


def find_image_plane(image_plane_name, collection_name=None):
    """Find a mesh object whose name contains image_plane_name."""
    if collection_name:
        collection = bpy.data.collections.get(collection_name)
        if not collection:
            return None
        objects = collection.all_objects
    else:
        objects = bpy.data.objects

    for obj in objects:
        if image_plane_name in obj.name:
            return obj
    return None


def set_key_frames(plane, start_frame=None, end_frame=None):
    """Animate an image sequence on a plane via frame_offset keyframes.

    Returns a list of {frame, timeline_frame, path} dicts, or None for a single
    image. NOTE (ported quirk): when start/end aren't passed it reads the scene
    frame range, so callers should set the scene range before calling.
    """
    image_frames = []

    if not plane or not plane.data.materials:
        raise ValueError("Plane must have at least one material.")
    if not start_frame:
        start_frame = bpy.context.scene.frame_start
    if not end_frame:
        end_frame = bpy.context.scene.frame_end

    mat = plane.data.materials[0]
    nodes = mat.node_tree.nodes
    tex_node = next((n for n in nodes if n.type == "TEX_IMAGE"), None)
    if not tex_node:
        raise RuntimeError("No image texture node found.")

    image = tex_node.image
    image_path = bpy.path.abspath(image.filepath)
    filename = os.path.basename(image_path)
    orig_frame_num = re.search(r"\.(\d{4})\.", filename).group(0)
    frame_numbers = get_frame_numbers(image_path)
    if not frame_numbers:
        raise RuntimeError("No matching sequence files found.")

    frame_count = end_frame - start_frame + 1
    if len(frame_numbers) == 1:
        image.source = "FILE"
        return None

    image.source = "SEQUENCE"
    tex_node.image_user.use_auto_refresh = True
    tex_node.image_user.frame_duration = frame_count
    tex_node.image_user.frame_start = start_frame

    previous_timeline_frame = None
    for image_frame in frame_numbers:
        timeline_frame = start_frame + image_frame
        image_frame_text = f".{image_frame:04d}."
        frame_num_path = image_path.replace(str(orig_frame_num), image_frame_text)
        image_frames.append(
            {"frame": image_frame, "timeline_frame": timeline_frame, "path": frame_num_path}
        )

        if previous_timeline_frame is not None:
            hold_frame = timeline_frame - 1
            hold_offset = -(hold_frame - previous_timeline_frame) - 1
            bpy.context.scene.frame_current = hold_frame
            tex_node.image_user.frame_offset = hold_offset
            tex_node.image_user.keyframe_insert(data_path="frame_offset")

        bpy.context.scene.frame_current = timeline_frame
        tex_node.image_user.frame_offset = -1
        tex_node.image_user.keyframe_insert(data_path="frame_offset")
        previous_timeline_frame = timeline_frame

    if end_frame is not None and previous_timeline_frame is not None:
        hold_offset = -(end_frame - previous_timeline_frame) - 1
        bpy.context.scene.frame_current = end_frame
        tex_node.image_user.frame_offset = hold_offset
        tex_node.image_user.keyframe_insert(data_path="frame_offset")

    return image_frames


def import_layer_to_image_plane(plane, image_path, full_prefix, sequence=True, char_name=True):
    """Load image_path onto plane, build a transparent material, and key the sequence.

    Returns (plane, plane_dict) on success, or None if the image is missing or the
    plane name has no parseable index.
    """
    if not os.path.exists(image_path):
        print(f"Image not found: {image_path}")
        return None

    plane_dict = {}
    _, _file = os.path.split(image_path)
    layer_name = _file.split(".")[0]
    new_layer_name = f"{full_prefix}{layer_name}_plane"

    if "_" in plane.name:
        parts = plane.name.split("_")
        plane_num = parts[-1].zfill(2) if parts[-1].isdigit() else "XX"
        short_id = f"ip{plane_num}"
    else:
        print(f"Plane name has no index: {plane.name}")
        return None

    if char_name:
        plane.name = new_layer_name

    material_name = f"{full_prefix}_{short_id}_mat"
    image_basename = os.path.splitext(os.path.basename(image_path))[0]
    image_name = f"{full_prefix}_{short_id}_{image_basename}_img"

    image = bpy.data.images.load(image_path, check_existing=False)
    image.name = image_name
    image.reload()

    mat = bpy.data.materials.new(name=material_name)
    plane.data.materials.append(mat)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output_node = nodes.new(type="ShaderNodeOutputMaterial")
    shader_node = nodes.new(type="ShaderNodeBsdfPrincipled")
    tex_node = nodes.new(type="ShaderNodeTexImage")
    tex_node.image = image

    _set_transparent_material(mat)

    links.new(tex_node.outputs["Color"], shader_node.inputs["Base Color"])
    links.new(tex_node.outputs["Alpha"], shader_node.inputs["Alpha"])
    links.new(shader_node.outputs["BSDF"], output_node.inputs["Surface"])

    image_frames = set_key_frames(plane)
    if image_frames:
        image.source = "SEQUENCE"
        plane_dict["image_frames"] = image_frames
    else:
        image.source = "FILE"
        plane_dict["image_frames"] = [
            {"frame": 0, "timeline_frame": 0, "path": image_path}
        ]

    plane.hide_select = True
    return plane, plane_dict
