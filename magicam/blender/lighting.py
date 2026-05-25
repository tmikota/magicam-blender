"""HDRI lighting picker — a thumbnail grid that builds the World on apply.

A ``template_icon_view`` grid (the matcap-style picker) backed by a previews
collection of the library's ``Name_thumb.png`` thumbnails. Applying sets up the
World with an Environment Texture + a Mapping rotation from the HDRI's ``yrot``
(its Y-up rotation mapped onto Blender's Z-up), so it comes in with the intended
direction. Reads the library from the JSON path in the add-on preferences.
"""

from __future__ import annotations

import math
import os

import bpy
import bpy.utils.previews

from magicam.blender import prefs

_previews = None
_hdri_enum_items = []  # keep a reference so Blender doesn't GC the enum strings
_library = None
_library_path = None


def _get_library(context=None):
    global _library, _library_path
    path = prefs.get_hdri_json_path()
    if not path or not os.path.exists(path):
        return None
    if _library is None or _library_path != path:
        from magicam.hdri import load_hdri_library

        _library = load_hdri_library(path)
        _library_path = path
    return _library


def _hdri_items(self, context):
    global _hdri_enum_items
    items = []
    lib = _get_library(context)
    if lib and _previews is not None:
        for entry in lib.entries:
            if not (entry.image_path and os.path.exists(entry.image_path)):
                continue  # skip entries with no loadable image (e.g. .tx-only)
            icon_id = 0
            if entry.thumb_path and os.path.exists(entry.thumb_path):
                if entry.name not in _previews:
                    try:
                        _previews.load(entry.name, entry.thumb_path, "IMAGE")
                    except Exception:
                        pass
                if entry.name in _previews:
                    icon_id = _previews[entry.name].icon_id
            items.append((entry.name, entry.name, "", icon_id, len(items)))
    if not items:
        items = [("NONE", "(no HDRIs)", "", 0, 0)]
    _hdri_enum_items = items
    return _hdri_enum_items


def _build_world_hdri(scene, image_path, yrot_degrees):
    """Set the scene World to an environment texture lit from image_path."""
    world = scene.world or bpy.data.worlds.new("MagiCam_World")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    mapping = nt.nodes.new("ShaderNodeMapping")
    texco = nt.nodes.new("ShaderNodeTexCoord")

    out.location = (600, 0)
    bg.location = (400, 0)
    env.location = (150, 0)
    mapping.location = (-100, 0)
    texco.location = (-300, 0)

    env.image = bpy.data.images.load(image_path, check_existing=True)
    # yrot is rotation about the up axis (Y-up source) -> Blender's Z.
    mapping.inputs["Rotation"].default_value[2] = math.radians(yrot_degrees)

    link = nt.links.new
    link(texco.outputs["Generated"], mapping.inputs["Vector"])
    link(mapping.outputs["Vector"], env.inputs["Vector"])
    link(env.outputs["Color"], bg.inputs["Color"])
    link(bg.outputs["Background"], out.inputs["Surface"])


class MagicamLightingState(bpy.types.PropertyGroup):
    hdri: bpy.props.EnumProperty(name="HDRI", items=_hdri_items)


class MAGICAM_OT_apply_hdri(bpy.types.Operator):
    bl_idname = "magicam.apply_hdri"
    bl_label = "Apply HDRI"
    bl_description = "Light the scene with the selected HDRI (sets the World)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = context.scene.magicam_lighting
        lib = _get_library(context)
        entry = lib.get(st.hdri) if lib else None
        if not entry or not entry.image_path or not os.path.exists(entry.image_path):
            self.report({"WARNING"}, f"HDRI '{st.hdri}' has no usable image.")
            return {"CANCELLED"}
        _build_world_hdri(context.scene, entry.image_path, entry.yrot)
        self.report({"INFO"}, f"World HDRI: {entry.name} (yrot {entry.yrot:g})")
        return {"FINISHED"}


class MAGICAM_PT_lighting(bpy.types.Panel):
    bl_label = "Lighting"
    bl_idname = "MAGICAM_PT_lighting"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MagiCam"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        if not _get_library(context):
            layout.label(text="Set the HDRI library JSON in add-on prefs.", icon="ERROR")
            return
        st = context.scene.magicam_lighting
        layout.template_icon_view(st, "hdri", show_labels=True, scale=6.0)
        layout.label(text=st.hdri)
        layout.operator("magicam.apply_hdri", icon="WORLD")


_classes = (MagicamLightingState, MAGICAM_OT_apply_hdri, MAGICAM_PT_lighting)


def register():
    global _previews
    _previews = bpy.utils.previews.new()
    for cls in _classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)
    bpy.types.Scene.magicam_lighting = bpy.props.PointerProperty(type=MagicamLightingState)


def unregister():
    global _previews, _library, _library_path
    if hasattr(bpy.types.Scene, "magicam_lighting"):
        del bpy.types.Scene.magicam_lighting
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    if _previews is not None:
        bpy.utils.previews.remove(_previews)
        _previews = None
    _library = None
    _library_path = None
