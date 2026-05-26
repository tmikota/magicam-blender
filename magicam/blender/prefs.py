"""Add-on preferences / config: paths to optional Alchemy + HDRI library.

Features degrade gracefully: with no Alchemy path the timeline import is
disabled, with no HDRI library the picker prompts for a path. Spot lights and
TVPaint import work with no config at all.
"""

from __future__ import annotations

import importlib.util
import os
import sys

import bpy

# The add-on/extension root module Blender keys preferences under: plain
# "magicam" as a library, or "bl_ext.<repo>.magicam" as an installed extension.
ADDON_ID = __package__.rpartition(".")[0]

_alc_cache: dict = {}


class MagicamPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_ID

    alchemy_path: bpy.props.StringProperty(
        name="Alchemy path",
        description=(
            "Folder containing the 'alc' package, added to sys.path so Alchemy "
            "features (timeline import) work. Leave blank if you don't use Alchemy."
        ),
        subtype="DIR_PATH",
        default="",
    )

    hdri_json_path: bpy.props.StringProperty(
        name="HDRI library (JSON)",
        description="Path to an HDRI library JSON (hdri.json). Leave blank to disable the HDRI picker.",
        subtype="FILE_PATH",
        default="",
    )

    enable_pipeline: bpy.props.BoolProperty(
        name="Enable Alchemy pipeline steps",
        description=(
            "Run optional Alchemy pipeline hooks during import (task structure, "
            "etc.). Requires Alchemy; off by default for standalone use."
        ),
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "alchemy_path")
        layout.label(
            text="Alchemy: " + ("found" if alc_available() else "not found"),
            icon="CHECKMARK" if alc_available() else "X",
        )
        layout.prop(self, "hdri_json_path")
        layout.prop(self, "enable_pipeline")
        layout.label(
            text="Camera rig template is bundled with the add-on.",
            icon="FILE_BLEND",
        )


def _prefs():
    try:
        return bpy.context.preferences.addons[ADDON_ID].preferences
    except (KeyError, AttributeError):
        return None


def get_hdri_json_path() -> str:
    p = _prefs()
    return p.hdri_json_path if p else ""


def get_enable_pipeline() -> bool:
    p = _prefs()
    return bool(p.enable_pipeline) if p else False


def get_alchemy_path() -> str:
    p = _prefs()
    return p.alchemy_path if p else ""


def ensure_alchemy_on_path() -> None:
    """Add the configured Alchemy folder to sys.path so 'alc' is importable."""
    path = get_alchemy_path()
    if path and os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)


def alc_available() -> bool:
    """Whether the 'alc' package is importable (after honoring the configured path)."""
    path = get_alchemy_path()
    if path not in _alc_cache:
        ensure_alchemy_on_path()
        _alc_cache[path] = importlib.util.find_spec("alc") is not None
    return _alc_cache[path]
