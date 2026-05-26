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


_spot_enum_items = []  # keep a reference so Blender doesn't GC the enum strings

SPOT_TAG = "magicam_spot"


def _spot_rigs():
    return [o for o in bpy.data.objects if o.get(SPOT_TAG)]


def _spot_light(control):
    """The SPOT light object parented under a control empty, if any."""
    if not control:
        return None
    for child in control.children:
        if child.type == "LIGHT" and child.data and child.data.type == "SPOT":
            return child
    return None


def _spot_items(self, context):
    global _spot_enum_items
    items = [(o.name, o.name, "") for o in _spot_rigs()]
    _spot_enum_items = items or [("NONE", "(no spot rigs)", "")]
    return _spot_enum_items


def _select_object(obj, tool="builtin.move"):
    """Make obj the sole selection/active in Object mode and set a transform tool."""
    try:
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass
    for o in list(bpy.context.selected_objects):
        o.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    try:
        bpy.ops.wm.tool_set_by_id(name=tool)
    except Exception as exc:
        print(f"[magicam] could not set tool '{tool}': {exc}")


def _snap_control_to_selection(context, control):
    """Move control to the selected geometry/object via the 3D cursor (restored after)."""
    scn = context.scene
    saved = scn.cursor.location.copy()
    try:
        bpy.ops.view3d.snap_cursor_to_selected()
    except Exception as exc:
        print(f"[magicam] snap to selection failed: {exc}")
        return False
    control.location = scn.cursor.location.copy()
    scn.cursor.location = saved
    return True


class MagicamLightingState(bpy.types.PropertyGroup):
    hdri: bpy.props.EnumProperty(name="HDRI", items=_hdri_items)
    spot: bpy.props.EnumProperty(name="Spot", items=_spot_items)
    spot_distance: bpy.props.FloatProperty(name="Distance", default=10.0, min=0.1)


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


class MAGICAM_OT_create_spot(bpy.types.Operator):
    bl_idname = "magicam.create_spot"
    bl_label = "Create Spot Light"
    bl_description = "Create an aim-rig spot light at the 3D cursor (control empty + offset spot)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = context.scene.magicam_lighting
        distance = st.spot_distance or 10.0

        n = 1
        while bpy.data.objects.get(f"MagiSpot_{n:02d}_ctrl"):
            n += 1
        base = f"MagiSpot_{n:02d}"

        empty = bpy.data.objects.new(f"{base}_ctrl", None)
        empty.empty_display_type = "SPHERE"
        empty.empty_display_size = 0.5
        empty[SPOT_TAG] = True
        empty.location = context.scene.cursor.location.copy()

        light_data = bpy.data.lights.new(base, "SPOT")
        # Inverse-square falloff: at `distance` units the light needs ~distance^2
        # more power to read. 150*d^2 reads instantly (~15000W at 10 units).
        light_data.energy = 150.0 * distance * distance
        light_obj = bpy.data.objects.new(base, light_data)
        light_obj.parent = empty
        light_obj.location = (0.0, 0.0, distance)  # up local +Z, default spot aims -Z back down
        light_obj.hide_select = True

        coll = context.collection
        coll.objects.link(empty)
        coll.objects.link(light_obj)

        _select_object(empty, "builtin.rotate")
        st.spot = empty.name
        self.report({"INFO"}, f"Created '{base}' ({distance:g} units)")
        return {"FINISHED"}


class MAGICAM_OT_select_spot_control(bpy.types.Operator):
    bl_idname = "magicam.select_spot_control"
    bl_label = "Select Spot Control"
    bl_description = "Select the spot's control and set the transform tool"
    tool: bpy.props.StringProperty(default="builtin.move")

    def execute(self, context):
        obj = bpy.data.objects.get(context.scene.magicam_lighting.spot)
        if not obj:
            return {"CANCELLED"}
        _select_object(obj, self.tool)
        return {"FINISHED"}


class MAGICAM_OT_snap_spot_to_selection(bpy.types.Operator):
    bl_idname = "magicam.snap_spot_to_selection"
    bl_label = "Snap Spot to Selection"
    bl_description = "Snap the spot's control to the selected vertex/face/object"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = bpy.data.objects.get(context.scene.magicam_lighting.spot)
        if not obj:
            return {"CANCELLED"}
        if not _snap_control_to_selection(context, obj):
            self.report({"WARNING"}, "Nothing selected to snap to.")
            return {"CANCELLED"}
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
        st = context.scene.magicam_lighting

        hdri = layout.box()
        hdri.label(text="HDRI", icon="WORLD")
        if _get_library(context):
            hdri.template_icon_view(st, "hdri", show_labels=True, scale=6.0)
            hdri.label(text=st.hdri)
            hdri.operator("magicam.apply_hdri", icon="WORLD")
        else:
            hdri.label(text="Set the HDRI library JSON in add-on prefs.", icon="ERROR")

        spots = layout.box()
        spots.label(text="Spot Lights", icon="LIGHT_SPOT")
        row = spots.row(align=True)
        row.prop(st, "spot_distance", text="Dist")
        row.operator("magicam.create_spot", text="Create")
        if _spot_rigs():
            spots.prop(st, "spot", text="")
            srow = spots.row(align=True)
            op = srow.operator("magicam.select_spot_control", text="Move")
            op.tool = "builtin.move"
            op = srow.operator("magicam.select_spot_control", text="Rotate")
            op.tool = "builtin.rotate"
            spots.operator("magicam.snap_spot_to_selection", icon="SNAP_ON")

            light = _spot_light(bpy.data.objects.get(st.spot))
            if light:
                spots.prop(light.data, "energy", text="Power")
                spots.prop(light.data, "spot_size", text="Cone")
                spots.prop(light.data, "color", text="")


_classes = (
    MagicamLightingState,
    MAGICAM_OT_apply_hdri,
    MAGICAM_OT_create_spot,
    MAGICAM_OT_select_spot_control,
    MAGICAM_OT_snap_spot_to_selection,
    MAGICAM_PT_lighting,
)


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
