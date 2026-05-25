"""Add-on preferences: the optional Alchemy pipeline seam toggle."""

from __future__ import annotations

import bpy

# Module path Blender registers this add-on under (see magicam/blender/__init__.py).
ADDON_ID = __package__  # "magicam.blender"


class MagicamPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_ID

    enable_pipeline: bpy.props.BoolProperty(
        name="Enable Alchemy pipeline steps",
        description=(
            "Run optional Alchemy pipeline hooks during import (task structure, "
            "etc.). Requires the alc package to be importable; off by default for "
            "standalone use."
        ),
        default=False,
    )

    hdri_json_path: bpy.props.StringProperty(
        name="HDRI library (JSON)",
        description="Path to the converted HDRI library JSON (hdri.json)",
        subtype="FILE_PATH",
        default=r"E:\Alchemy\cgl\config\CGL-HDRI\hdri.json",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "enable_pipeline")
        layout.prop(self, "hdri_json_path")
        layout.label(
            text="Rig template is bundled with the add-on (resources/).",
            icon="FILE_BLEND",
        )


def get_hdri_json_path() -> str:
    try:
        return bpy.context.preferences.addons[ADDON_ID].preferences.hdri_json_path
    except (KeyError, AttributeError):
        return r"E:\Alchemy\cgl\config\CGL-HDRI\hdri.json"


def get_enable_pipeline() -> bool:
    """Read the pipeline toggle, defaulting to False if prefs aren't registered."""
    try:
        return bool(bpy.context.preferences.addons[ADDON_ID].preferences.enable_pipeline)
    except (KeyError, AttributeError):
        return False
