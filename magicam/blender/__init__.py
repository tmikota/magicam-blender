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

from magicam.blender import caddy_blender, ops, panels, prefs

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


def unregister():
    try:
        from magicam.blender import scene as _scene

        _scene.disable_multicam_playback()
    except Exception:
        pass
    caddy_blender.unregister()
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
