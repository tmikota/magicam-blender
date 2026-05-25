"""Validate the TVPaint query layer against known values from both sample exports.

Run with a Python that has pydantic 2 installed.
"""

import sys
from pathlib import Path

from magicam.tvpaint import load_clip, query

V11 = Path(r"C:\Users\tmiko\_export\tvpaint_11\clip_export.json")
V12 = Path(r"C:\Users\tmiko\_export\tvpaint_12\clip_export.json")

_passed = 0
_failed = 0


def check(label, got, expected):
    global _passed, _failed
    ok = got == expected
    _passed += ok
    _failed += not ok
    status = "ok " if ok else "FAIL"
    print(f"  [{status}] {label}: {got!r}" + ("" if ok else f"  != expected {expected!r}"))


def main() -> int:
    if V11.exists():
        print(f"\n=== tvpaint_11: {V11} ===")
        check("layer_names", query.layer_names(V11),
              ["Anim_16", "Anim_14", "Anim_12", "Anim_01", "Anim_18"])
        check("layer_names(filter=['Anim_1'])", query.layer_names(V11, ["Anim_1"]), ["Anim_01"])
        check("frame_range_from_layers", query.frame_range_from_layers(V11), (0, 52))
        check("shot_frame_range", query.shot_frame_range(V11), "0-0")
        check("layer_frame_range(None)", query.layer_frame_range(V11), "1-1")
        check("get_first_image_name('Anim_16')",
              query.get_first_image_name(V11, "Anim_16"), "Anim_16.0000.png")
        check("get_first_image_name('Anim_16', include_folder)",
              query.get_first_image_name(V11, "Anim_16", include_folder=True),
              ["Clip_134.000.Anim_16", "Anim_16.0000.png"])
        check("Anim_12 frame_range_string (3 links)",
              load_clip(V11).clip.layer("Anim_12").frame_range_string(), "1,26,43")
        check("layer_images('Anim_16')[0]", query.layer_images(V11, "Anim_16")[0],
              str(V11.parent / "Clip_134.000.Anim_16/Anim_16.0000.png"))

    if V12.exists():
        print(f"\n=== tvpaint_12: {V12} ===")
        check("len(layer_names)", len(query.layer_names(V12)), 14)
        check("frame_range_from_layers", query.frame_range_from_layers(V12), (0, 90))
        check("shot_frame_range", query.shot_frame_range(V12), "0-90")
        check("layer_frame_range(None)", query.layer_frame_range(V12), "1-91")
        check("get_first_image_name('Anim_19')",
              query.get_first_image_name(V12, "Anim_19"), "Anim_19.0000.png")
        check("Anim_19 frame_range_string (12 links)",
              load_clip(V12).clip.layer("Anim_19").frame_range_string(), "1,46-56")
        check("layer_images('Anim_19')[0]", query.layer_images(V12, "Anim_19")[0],
              str(V12.parent / "Clip_139_001.Anim_19/Anim_19.0000.png"))

        # input-type compatibility: path vs dict vs model give identical results
        import json
        as_dict = json.loads(V12.read_text(encoding="utf-8"))
        as_model = load_clip(V12)
        check("compat: layer_names(dict) == layer_names(path)",
              query.layer_names(as_dict), query.layer_names(V12))
        check("compat: layer_images(model) resolves via source_dir",
              query.layer_images(as_model, "Anim_19")[0],
              str(V12.parent / "Clip_139_001.Anim_19/Anim_19.0000.png"))

    print(f"\n{'ALL PASSED' if not _failed else 'FAILED'}  ({_passed} passed, {_failed} failed)")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
