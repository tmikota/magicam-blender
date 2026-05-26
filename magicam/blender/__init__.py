"""MagiCam — multiplane camera tooling for Blender (PySide-free).

Register from Blender's Python console or a Text-editor script:

    import magicam.blender as mb
    mb.register()

(make sure the magicam-blender repo is on sys.path first).
"""

from __future__ import annotations

bl_info = {
    "name": "MagiCam",
    "author": "Tom Mikota",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > MagiCam",
    "description": "Build multiplane camera rigs from TVPaint clip exports.",
    "category": "Camera",
}

import bpy

from . import caddy_blender, lighting, ops, panels, prefs

_classes = (prefs.MagicamPreferences, *ops.classes, *panels.classes)


def register():
    for cls in _classes:
        # Tolerate a re-run in the same session (re-register cleanly).
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)
    caddy_blender.register()
    lighting.register()


def unregister():
    try:
        from . import scene as _scene

        _scene.disable_multicam_playback()
    except Exception:
        pass
    lighting.unregister()
    caddy_blender.unregister()
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass


# --- public entry points for build recipes ---------------------------------
# Lazy imports: `timeline` pulls in `alc`, so importing it here would stop the
# add-on registering for users without Alchemy. Calling these does the import.

def import_alchemy_timeline(timeline_json_path):
    """Build a camera per storyboard + audio from an Alchemy scene_*_timeline.json.

    Requires the `alc` package (for path resolution). Returns (cameras, audio_strips).
    """
    from . import timeline

    return timeline.import_alchemy_timeline(timeline_json_path)


def import_multicam_rig(tvpaint_json, shot_name=None, **kwargs):
    """Build a TVPaint multiplane camera rig from a clip_export.json."""
    from . import build

    return build.import_multicam_rig(tvpaint_json, shot_name=shot_name, **kwargs)
