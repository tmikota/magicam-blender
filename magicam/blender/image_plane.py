"""Image-plane material setup and image-sequence keyframing.

Ported PySide-free from the cglumberjack image_plane tool and the original
multiplaneCamera create.py.
"""

from __future__ import annotations

import os
import re

import bpy

# Image planes import slightly knocked back by default (reference-friendly).
DEFAULT_PLANE_OPACITY = 0.85

# Mapping node that fits a non-plane-aspect image inside the plane. Named so a
# re-import can find it rather than stacking a second one.
_FIT_NODE = "magicam_aspect_fit"


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


def fit_uv_scale(image_aspect, plane_aspect):
    """UV scale factors that letterbox/pillarbox an image inside a plane.

    Pure math, no bpy — the aspect decision, isolated so it can be tested.

    Returns ``(scale_x, scale_y)`` to apply to the UVs. Scaling UVs UP shows MORE
    than the image (the surplus falls outside 0..1 and clips to transparent), which
    is what puts the bars in. The image itself is never distorted: exactly one axis
    is ever scaled.
    """
    if image_aspect <= 0 or plane_aspect <= 0:
        return 1.0, 1.0
    if image_aspect > plane_aspect:
        # Image is wider than the plane: fit to width, bars top and bottom.
        return 1.0, image_aspect / plane_aspect
    # Image is taller than the plane: fit to height, bars left and right.
    return plane_aspect / image_aspect, 1.0


def _plane_aspect(plane):
    """A plane object's own width:height, whatever its orientation.

    Read from world-space ``dimensions`` (so object scale counts) by taking the two
    non-degenerate axes — the planes are rotated to face the camera, so which axes
    those are depends on the rig.
    """
    dims = sorted((abs(d) for d in plane.dimensions), reverse=True)
    width, height = dims[0], dims[1]
    return width / height if height else 0.0


def fit_image_to_plane(mat, plane, image):
    """Fit the image INSIDE the plane at its own aspect instead of stretching it.

    The image planes are prebuilt quads appended with the camera rig, and the default
    UV map stretches whatever is loaded onto them to fill the whole quad — so a board
    that isn't the plane's aspect comes in distorted (a 4:3 board on a 16:9 plane
    makes the character wider than they were drawn).

    This scales the UVs, NOT the geometry: the plane keeps its dimensions and goes on
    standing in for the camera frame, while the drawing keeps its shape. The area the
    image doesn't reach clips to transparent, which reads as letterbox/pillarbox bars.
    """
    if not mat or not mat.use_nodes or not image:
        return None
    img_w, img_h = image.size
    if not img_w or not img_h:
        return None

    plane_aspect = _plane_aspect(plane)
    if not plane_aspect:
        return None
    image_aspect = img_w / img_h

    nt = mat.node_tree
    tex_node = next((n for n in nt.nodes if n.type == "TEX_IMAGE"), None)
    if not tex_node:
        return None

    # Outside the image, sample transparent rather than repeating it — the bars.
    tex_node.extension = "CLIP"

    scale_x, scale_y = fit_uv_scale(image_aspect, plane_aspect)
    if abs(scale_x - 1.0) < 1e-4 and abs(scale_y - 1.0) < 1e-4:
        # Already the plane's aspect — leave the UVs alone (the common 16:9 case).
        return None

    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.name = _FIT_NODE
    mapping.label = "MagiCam Aspect Fit"
    tex_coord = nt.nodes.new("ShaderNodeTexCoord")

    # The Mapping node scales about the UV ORIGIN, so offset to keep the image
    # centred: out = uv*s + 0.5*(1-s) is uv scaled about (0.5, 0.5).
    mapping.inputs["Scale"].default_value = (scale_x, scale_y, 1.0)
    mapping.inputs["Location"].default_value = (
        0.5 * (1.0 - scale_x),
        0.5 * (1.0 - scale_y),
        0.0,
    )

    nt.links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], tex_node.inputs["Vector"])
    return mapping


def _build_transparent_image_material(image, material_name):
    """A Principled material wired for an alpha-blended image (Color + Alpha)."""
    mat = bpy.data.materials.new(name=material_name)
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
    return mat


def apply_static_image(plane, image_path, full_prefix, new_name=None):
    """Put a single still image (not a sequence) on a plane with a transparent material.

    Used for Alchemy storyboards, which are single flattened PNGs. Returns the
    plane, or None if the image is missing.
    """
    if not os.path.exists(image_path):
        print(f"Image not found: {image_path}")
        return None
    if new_name:
        plane.name = new_name

    base = os.path.splitext(os.path.basename(image_path))[0]
    image = bpy.data.images.load(image_path, check_existing=False)
    image.name = f"{full_prefix}{base}_img"
    image.source = "FILE"

    mat = _build_transparent_image_material(image, f"{full_prefix}{base}_mat")
    plane.data.materials.append(mat)
    fit_image_to_plane(mat, plane, image)
    set_plane_opacity(plane, DEFAULT_PLANE_OPACITY)
    plane.hide_select = True
    return plane


_OPACITY_NODE = "magicam_opacity"


def _ensure_opacity_node(mat):
    """Insert/return a MULTIPLY node feeding Principled Alpha.

    The image's alpha is multiplied by an opacity factor, so opacity fades the
    plane while preserving its cutout alpha (a linked Alpha socket ignores its
    own default_value, which is why setting Alpha directly does nothing).
    """
    if not mat or not mat.use_nodes:
        return None
    nt = mat.node_tree
    principled = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not principled:
        return None
    alpha_in = principled.inputs["Alpha"]
    for link in alpha_in.links:
        if link.from_node.name == _OPACITY_NODE:
            return link.from_node

    src_socket = alpha_in.links[0].from_socket if alpha_in.links else None
    mult = nt.nodes.new("ShaderNodeMath")
    mult.name = _OPACITY_NODE
    mult.label = "MagiCam Opacity"
    mult.operation = "MULTIPLY"
    mult.inputs[1].default_value = 1.0
    if src_socket:
        nt.links.new(src_socket, mult.inputs[0])
    else:
        mult.inputs[0].default_value = 1.0
    nt.links.new(mult.outputs[0], alpha_in)
    return mult


def set_plane_opacity(obj, value):
    """Set overall opacity (0..1) on every material of an image plane."""
    for slot in obj.material_slots:
        node = _ensure_opacity_node(slot.material)
        if node:
            node.inputs[1].default_value = value


def get_plane_opacity(obj):
    """Read an image plane's opacity factor (1.0 if none set)."""
    for slot in obj.material_slots:
        mat = slot.material
        if mat and mat.use_nodes:
            node = mat.node_tree.nodes.get(_OPACITY_NODE)
            if node:
                return node.inputs[1].default_value
            principled = next(
                (n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None
            )
            if principled:
                return principled.inputs["Alpha"].default_value
    return 1.0


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

    fit_image_to_plane(mat, plane, image)

    image_frames = set_key_frames(plane)
    if image_frames:
        image.source = "SEQUENCE"
        plane_dict["image_frames"] = image_frames
    else:
        image.source = "FILE"
        plane_dict["image_frames"] = [
            {"frame": 0, "timeline_frame": 0, "path": image_path}
        ]

    set_plane_opacity(plane, DEFAULT_PLANE_OPACITY)
    plane.hide_select = True
    return plane, plane_dict


def static_image_plane(image_plane_object):
    """Duplicate a SEQUENCE-based plane as a standalone plane showing the current frame."""
    if (
        not image_plane_object
        or not image_plane_object.data
        or not image_plane_object.data.materials
    ):
        raise ValueError("Image plane must have at least one material.")

    new_obj = image_plane_object.copy()
    new_obj.data = image_plane_object.data.copy()
    new_obj.name = f"{image_plane_object.name}_static"
    new_obj.matrix_world = image_plane_object.matrix_world.copy()
    new_obj.parent = None
    new_obj.matrix_parent_inverse.identity()
    new_obj.constraints.clear()

    if new_obj.animation_data and new_obj.animation_data.drivers:
        for fcurve in list(new_obj.animation_data.drivers):
            new_obj.driver_remove(fcurve.data_path, fcurve.array_index)

    mat = new_obj.data.materials[0]
    if mat and mat.use_nodes:
        image_node = next(
            (n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE"), None
        )
        static_image = query_current_image_from_sequence(image_node)
        if static_image:
            set_image_plane_to_single_image(image_node, static_image)

    for coll in image_plane_object.users_collection:
        coll.objects.link(new_obj)
    new_obj.hide_select = False
    return new_obj


def query_current_image_from_sequence(image_node):
    """Load the single image shown at the current frame for a SEQUENCE texture node."""
    if not image_node or not image_node.image or image_node.image.source != "SEQUENCE":
        print("Not a valid sequence image node.")
        return None

    img = image_node.image
    user = image_node.image_user
    scene_frame = bpy.context.scene.frame_current
    total_frames = user.frame_duration or img.frame_duration
    frame_idx = scene_frame - user.frame_start + user.frame_offset
    if frame_idx < 0 or frame_idx >= total_frames:
        print(f"Frame {scene_frame} out of range (index {frame_idx}).")
        return None

    filepath = bpy.path.abspath(img.filepath)
    directory = os.path.dirname(filepath)
    base, ext = os.path.splitext(os.path.basename(filepath))
    digits = "".join(filter(str.isdigit, base))
    pad = len(digits) if digits else 4
    base_no_digits = base[:-pad] if digits else base
    frame_str = str(frame_idx + 1).zfill(pad)
    static_path = os.path.join(directory, f"{base_no_digits}{frame_str}{ext}")

    try:
        return bpy.data.images.load(static_path)
    except Exception as exc:
        print(f"Failed to load image '{static_path}': {exc}")
        return None


def set_image_plane_to_single_image(image_node, static_image):
    """Switch a texture node from SEQUENCE to a single static image."""
    if not image_node or not static_image:
        return
    image_node.image = static_image
    image_node.image.source = "FILE"
    image_node.image_user.use_auto_refresh = False
    image_node.image_user.frame_offset = 0
    image_node.image_user.frame_duration = 1
    image_node.image_user.frame_start = 1
