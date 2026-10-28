"""Variable image-plane count (#4594), run inside Blender:

    blender -b --factory-startup --python validate_plane_count.py -- [clip_export.json]

Checks 10 (no change), 11, the cap, idempotence, that a cloned control bone really moves its plane,
and - when a clip_export.json is given - that a full import builds one plane per layer.
"""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from magicam.blender import rig, scene  # noqa: E402

PREFIX = "T_"


def fresh_rig():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    coll = rig.append_camera_rig(
        rig.default_rig_template_path(), "magicCam", "CAM_T", link_into_scene=True
    )
    rig.namespace_everything(coll, PREFIX)
    return coll, scene.armature_object("CAM_T")


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        raise SystemExit(1)


coll, arm = fresh_rig()
check(rig.plane_count(PREFIX) == 10, "bundled rig has 10 planes")
rig.ensure_plane_count(arm, PREFIX, 10)
check(rig.plane_count(PREFIX) == 10, "asking for 10 changes nothing")

rig.ensure_plane_count(arm, PREFIX, 11)
check(rig.plane_count(PREFIX) == 11, "asking for 11 builds one more plane")
rig.ensure_plane_count(arm, PREFIX, 11)
check(rig.plane_count(PREFIX) == 11, "asking for 11 again is idempotent")

p10, p11 = (bpy.data.objects[f"{PREFIX}image_plane_{n}"] for n in (10, 11))
check(abs(p11.location.y - (p10.location.y + rig.PLANE_SPACING)) < 1e-6, "plane 11 sits behind 10")
check(p11.animation_data and len(p11.animation_data.drivers) == 2, "plane 11 kept its frustum drivers")
con = p11.constraints[0]
check(con.targets[0].subtarget == f"{PREFIX}image_plane_11_ctrl", "plane 11 follows its own control bone")
check(p10.constraints[0].targets[0].subtarget == f"{PREFIX}image_plane_10_ctrl", "plane 10 untouched")
check(p11.data is not p10.data, "plane 11 has its own mesh")
check(p11.users_collection == p10.users_collection, "plane 11 is in the same collection")

b10 = arm.pose.bones[f"{PREFIX}image_plane_10_ctrl"]
b11 = arm.pose.bones[f"{PREFIX}image_plane_11_ctrl"]
check(b11.parent == b10.parent, "control bone 11 shares the parent")
check(b11.custom_shape == b10.custom_shape, "control bone 11 shares the shape")
check(
    [c.name for c in b11.bone.collections] == [c.name for c in b10.bone.collections],
    "control bone 11 is in the same bone collection",
)
check(
    b11.constraints[0].min_y == b10.constraints[0].min_y - rig.PLANE_SPACING,
    "its location floor moved with it",
)

# the control bone really moves the plane
bpy.context.view_layer.update()
before = p11.matrix_world.translation.y
before10 = p10.matrix_world.translation.y
b11.location.y = -3.0
bpy.context.view_layer.update()
check(abs(abs(p11.matrix_world.translation.y - before) - 3.0) < 1e-3, "moving control bone 11 moves plane 11")
check(abs(p10.matrix_world.translation.y - before10) < 1e-3, "and does not move plane 10")

rig.ensure_plane_count(arm, PREFIX, rig.MAX_PLANES)
check(rig.plane_count(PREFIX) == rig.MAX_PLANES, "builds up to the cap")
try:
    rig.ensure_plane_count(arm, PREFIX, rig.MAX_PLANES + 1)
    check(False, "over the cap raises")
except ValueError as exc:
    check("at most" in str(exc), "over the cap raises a clear error")

args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
if args:
    import magicam.blender as mb
    from magicam.tvpaint import query as tvp_query

    bpy.ops.wm.read_factory_settings(use_empty=True)
    n_layers = len(tvp_query.tvp_data(args[0]).clip.layers)
    mb.import_multicam_rig(args[0], shot_name="")
    arm_obj = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    planes = next(iter(scene.load_camera_data_from_armature(arm_obj)["cameras"].values()))["camera_planes"]
    check(len(planes) == n_layers, f"full import: {len(planes)} planes built for {n_layers} layers")
    for name, entry in planes.items():
        check(entry["control_bone"] in arm_obj.pose.bones, f"{name} has its control bone")
        check(not bpy.data.objects[name].hide_viewport, f"{name} is visible")

print("ALL PASS")
