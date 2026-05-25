"""Validate that the TVPaint models round-trip both v11 and v12 exports losslessly.

Loads each sample clip_export.json, dumps the model back to a dict (by alias,
dropping unset/version-specific fields), and compares it to the source JSON.
Run with a Python that has pydantic 2 installed.
"""

import json
import sys
from pathlib import Path

from magicam.tvpaint import load_clip

SAMPLES = {
    "tvpaint_11": Path(r"C:\Users\tmiko\_export\tvpaint_11\clip_export.json"),
    "tvpaint_12": Path(r"C:\Users\tmiko\_export\tvpaint_12\clip_export.json"),
}


def _diff_paths(a, b, prefix=""):
    """Yield human-readable paths where dicts/lists a and b differ."""
    if isinstance(a, dict) and isinstance(b, dict):
        for key in a.keys() | b.keys():
            if key not in a:
                yield f"{prefix}{key}: missing in round-trip"
            elif key not in b:
                yield f"{prefix}{key}: extra in round-trip"
            else:
                yield from _diff_paths(a[key], b[key], f"{prefix}{key}.")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield f"{prefix[:-1]}: list length {len(a)} != {len(b)}"
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                yield from _diff_paths(x, y, f"{prefix}[{i}].")
    elif a != b:
        yield f"{prefix[:-1]}: {a!r} != {b!r}"


def main() -> int:
    failures = 0
    for label, path in SAMPLES.items():
        print(f"\n=== {label}: {path} ===")
        if not path.exists():
            print(f"   SKIP (not found)")
            continue

        source = json.loads(path.read_text(encoding="utf-8"))
        export = load_clip(path)
        clip = export.clip

        print(f"  clip name      : {clip.name}")
        print(f"  resolution     : {clip.width}x{clip.height} @ {clip.framerate}fps")
        print(f"  image-count    : {clip.image_count}")
        print(f"  layers         : {len(clip.layers)} -> {[l.name for l in clip.layers]}")
        print(f"  camera.profile : {clip.camera.profile!r} (v11 only)")
        print(f"  markin/markout : {clip.markin} / {clip.markout} (v12 only)")
        print(f"  cam positions  : {len(clip.camera.positions)}")

        roundtrip = export.model_dump(by_alias=True, exclude_none=True)
        diffs = list(_diff_paths(source, roundtrip))
        if diffs:
            failures += 1
            print(f"  ROUND-TRIP MISMATCH ({len(diffs)} differences):")
            for d in diffs[:40]:
                print(f"    - {d}")
        else:
            print("  ROUND-TRIP: OK (lossless)")

    print(f"\n{'FAILED' if failures else 'ALL PASSED'} ({failures} file(s) with diffs)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
