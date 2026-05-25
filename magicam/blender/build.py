"""Top-level orchestration: build a multiplane camera rig from a TVPaint export.

PySide-free port of multiplaneCamera create.multicam_rig. Pipeline coupling
(task structure / asset import) lives behind the ``enable_pipeline`` seam and is
off by default, so this runs against the current .blend with no Alchemy install.
"""

from __future__ import annotations

import os
import re

import bpy

from magicam.blender import image_plane, rig, scene
from magicam.tvpaint import query as tvp_query


def shot_name_from_clip(clip_name: str) -> str:
    """Derive a Blender-safe, uppercased shot name from a TVPaint clip name.

    e.g. "Clip_139" -> "CLIP_139"; "Clip_134 - v2" -> "CLIP_134_V2".
    """
    cleaned = re.sub(r"[^A-Z0-9_]+", "_", clip_name.upper())
    return cleaned.strip("_") or "CLIP"


def _pipeline_pre(shot_name):
    """Optional Alchemy hook (task structure etc.). Best-effort; never fatal."""
    try:
        import alc.plugins.blender.create as bpy_create

        bpy_create.task_structure("storyviz")
    except Exception as exc:  # pragma: no cover - depends on external pipeline
        print(f"[magicam] pipeline pre-step skipped: {exc}")


def import_multicam_rig(
    tvpaint_json,
    shot_name=None,
    shot_start_frame=None,
    timeline_start_frame=None,
    enable_pipeline=False,
):
    """Append the rig, build an image plane per TVPaint layer, and wire playback.

    Returns the rig collection, or None if nothing was created.
    """
    if not os.path.exists(tvpaint_json):
        print(f"TVPaint JSON not found: {tvpaint_json}")
        return None

    if enable_pipeline:
        _pipeline_pre(shot_name)

    export = tvp_query.tvp_data(tvpaint_json)
    if not shot_name:
        shot_name = shot_name_from_clip(export.clip.name)

    rig_collection = f"CAM_{shot_name}"
    scene_children = [c.name for c in bpy.context.scene.collection.children]
    if rig_collection in bpy.data.collections and rig_collection in scene_children:
        print(f"Rig collection '{rig_collection}' already in scene — skipping.")
        return None

    rig_path = rig.default_rig_template_path()
    rig_collection_object = rig.append_camera_rig(
        blend_file=rig_path,
        source_collection_name="magicCam",
        dest_collection_name=rig_collection,
        link_into_scene=True,
    )

    armature_obj = scene.armature_object(rig_collection)
    prefix = f"{shot_name}_"
    rig.namespace_everything(rig_collection_object, prefix)
    camera_name = f"{prefix}MagiCam"

    start_frame, end_frame = export.clip.frame_range_from_layers()
    if not shot_start_frame:
        shot_start_frame = start_frame or 1
    duration = end_frame - start_frame
    shot_end_frame = shot_start_frame + duration

    camera_data = {
        "start_frame": shot_start_frame,
        "end_frame": shot_end_frame,
        "shot_name": shot_name,
        "prefix": prefix,
        "cameras": {camera_name: {"camera_planes": {}}},
    }
    camera_planes = camera_data["cameras"][camera_name]["camera_planes"]

    json_dir = os.path.dirname(tvpaint_json)
    for i, layer in enumerate(export.clip.layers):
        image_plane_number = str(i + 1).zfill(2)
        image_plane_name = f"{prefix}image_plane_{image_plane_number}"
        imp_obj = image_plane.find_image_plane(image_plane_name)
        if not imp_obj:
            # The bundled rig provides 10 planes; extra layers are skipped.
            print(f"No rig plane for layer #{i + 1} ('{layer.name}') — skipping.")
            continue
        if not layer.link:
            print(f"Layer '{layer.name}' has no linked image — skipping.")
            continue

        image_path = os.path.join(json_dir, layer.link[0].file).replace("\\", "/")
        result = image_plane.import_layer_to_image_plane(
            imp_obj, image_path, prefix, sequence=True
        )
        if not result:
            continue
        plane_, plane_dict = result
        plane_dict["control_bone"] = f"{prefix}image_plane_{image_plane_number}_ctrl"
        camera_planes[plane_.name] = plane_dict

        scene.key_visibility(plane_.name, int(shot_start_frame))
        scene.key_visibility(plane_.name, int(shot_end_frame))
        scene.key_visibility(plane_.name, int(shot_start_frame) - 1, visible=False)
        scene.key_visibility(plane_.name, int(shot_end_frame) + 1, visible=False)

    scene.store_camera_data_on_armature(armature_obj, camera_data)

    scene.hide_image_planes_without_material(prefix)
    rig.hide_after_append(rig_collection_object, prefix)
    scene.toggle_image_plane_controls(prefix)

    scene.ensure_collection("CAM")
    scene.move_collection_to_collection(rig_collection_object, "CAM")

    scene.set_frame_range(
        timeline_start_frame if timeline_start_frame else shot_start_frame,
        shot_end_frame,
        current=shot_start_frame,
    )

    camera_obj = scene.camera_object("MagiCam", rig_collection_object.name)
    if camera_obj:
        scene.timeline_mark(rig_collection, frame=shot_start_frame, camera_obj=camera_obj)
        scene.enable_multicam_playback()

    # Force a depsgraph re-evaluation so image-driven plane sizes refresh at
    # load, instead of staying at rig defaults until visibility is toggled.
    bpy.context.view_layer.update()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)

    return rig_collection_object
