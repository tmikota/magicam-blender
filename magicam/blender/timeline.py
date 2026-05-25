"""Build a MagiCam scene from an Alchemy edit timeline.

Each storyboard Image clip becomes its own camera rig (one image plane showing
that board), placed at its absolute timeline frame with a marker; the existing
camera-switch handler plays them in sequence. Audio clips become VSE sound
strips. Plane visibility is keyed to each clip's span so only the current board
shows.

This module requires Alchemy: storyboard/audio paths are resolved with
``alc.path.media_to_abs``. It's imported lazily by the operator so the rest of
the add-on still registers without alc installed.
"""

from __future__ import annotations

import os

import bpy
from alc.path import media_to_abs

from magicam.alchemy import load_timeline
from magicam.blender import image_plane, rig, scene


def _scene_children_names():
    return [c.name for c in bpy.context.scene.collection.children]


def _build_storyboard_camera(clip, abs_start, duration, scene_prefix):
    """Append a rig for one storyboard board and place it on the timeline."""
    shot = f"{scene_prefix}{clip.name}"
    rig_collection = f"CAM_{shot}"
    if rig_collection in bpy.data.collections and rig_collection in _scene_children_names():
        print(f"Rig '{rig_collection}' already in scene — skipping.")
        return None

    rig_path = rig.default_rig_template_path()
    rig_obj = rig.append_camera_rig(
        rig_path, "magicCam", rig_collection, link_into_scene=True
    )
    armature = scene.armature_object(rig_collection)
    prefix = f"{shot}_"
    rig.namespace_everything(rig_obj, prefix)
    camera_name = f"{prefix}MagiCam"

    start_f = abs_start + 1  # Blender timelines are 1-based
    end_f = abs_start + duration

    camera_planes = {}
    plane_obj = image_plane.find_image_plane(f"{prefix}image_plane_01")
    img_path = media_to_abs(clip.media_url) if clip.media_url else None
    if plane_obj and img_path and os.path.exists(img_path):
        image_plane.apply_static_image(
            plane_obj, img_path, prefix, new_name=f"{prefix}{clip.name}_plane"
        )
        camera_planes[plane_obj.name] = {
            "control_bone": f"{prefix}image_plane_01_ctrl",
            "image_frames": [
                {"frame": 0, "timeline_frame": start_f, "path": img_path}
            ],
        }
        scene.key_visibility(plane_obj.name, start_f)
        scene.key_visibility(plane_obj.name, end_f)
        scene.key_visibility(plane_obj.name, start_f - 1, visible=False)
        scene.key_visibility(plane_obj.name, end_f + 1, visible=False)
    else:
        print(f"No image for storyboard '{clip.name}' ({clip.media_url}).")

    camera_data = {
        "start_frame": start_f,
        "end_frame": end_f,
        "shot_name": shot,
        "prefix": prefix,
        "block_id": clip.block_id,
        "cameras": {camera_name: {"camera_planes": camera_planes}},
    }
    scene.store_camera_data_on_armature(armature, camera_data)

    scene.hide_image_planes_without_material(prefix)
    rig.hide_after_append(rig_obj, prefix)
    scene.toggle_image_plane_controls(prefix)
    scene.ensure_collection("CAM")
    scene.move_collection_to_collection(rig_obj, "CAM")

    cam_obj = scene.camera_object("MagiCam", rig_obj.name)
    if cam_obj:
        scene.timeline_mark(rig_collection, frame=start_f, camera_obj=cam_obj)
    return rig_obj


def _audio_strips(timeline):
    """Add each audio clip as a VSE sound strip at its absolute frame."""
    scn = bpy.context.scene
    if not scn.sequence_editor:
        scn.sequence_editor_create()
    se = scn.sequence_editor
    # Blender 5.x renamed sequences -> strips. Check existence rather than using
    # `or`, since an empty collection is falsy and would wrongly fall through.
    strips = se.strips if hasattr(se, "strips") else se.sequences

    added = 0
    for clip, abs_start, _dur in timeline.audio_clips():
        path = media_to_abs(clip.media_url) if clip.media_url else None
        if not path or not os.path.exists(path):
            print(f"Audio not found: {clip.media_url}")
            continue
        try:
            strips.new_sound(
                name=clip.name, filepath=path, channel=1, frame_start=abs_start + 1
            )
            added += 1
        except Exception as exc:
            print(f"Could not add audio '{clip.name}': {exc}")
    return added


def import_alchemy_timeline(path):
    """Build cameras + audio for an Alchemy ``scene_*_timeline.json``.

    Returns (cameras_built, audio_added).
    """
    timeline = load_timeline(path)
    scene_prefix = f"{timeline.scene_id}_" if timeline.scene_id else ""

    built = 0
    for clip, abs_start, duration in timeline.storyboard_clips():
        if _build_storyboard_camera(clip, abs_start, duration, scene_prefix):
            built += 1

    audio_added = _audio_strips(timeline)

    total = timeline.total_frames()
    scene.set_frame_range(1, total if total else bpy.context.scene.frame_end, current=1)
    scene.enable_multicam_playback()

    # Mirror the import refresh so plane sizes settle at load.
    bpy.context.view_layer.update()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    return built, audio_added
