"""Validate the Alchemy timeline model against a sample scene_*_timeline.json.

Run with a Python that has pydantic 2 installed.
"""

import sys
from pathlib import Path

from magicam.alchemy import load_timeline

SAMPLE = Path(
    r"E:\Alchemy\cgl\pip\VERSIONS\source\shots\010\SEQ\svz\default\tom"
    r"\000.000\high\scene_010_timeline.json"
)

_passed = 0
_failed = 0


def check(label, got, expected):
    global _passed, _failed
    ok = got == expected
    _passed += ok
    _failed += not ok
    print(f"  [{'ok ' if ok else 'FAIL'}] {label}: {got!r}"
          + ("" if ok else f"  != {expected!r}"))


def main() -> int:
    if not SAMPLE.exists():
        print(f"SKIP (not found): {SAMPLE}")
        return 0

    tl = load_timeline(SAMPLE)
    print(f"timeline: {tl.name}  scene_id={tl.scene_id}  total_frames={tl.total_frames()}")

    sb = list(tl.storyboard_clips())
    au = list(tl.audio_clips())
    print(f"storyboard images: {len(sb)}   audio clips: {len(au)}")

    print("\nfirst storyboard clips (name, abs_start, duration):")
    for clip, start, dur in sb[:5]:
        print(f"   {clip.name:12} start={start:5} dur={dur}")

    # storyboard offsets
    check("sb[0] (0010_001)", (sb[0][0].name, sb[0][1], sb[0][2]), ("0010_001", 0, 134))
    check("sb[1] (0020_001)", (sb[1][0].name, sb[1][1], sb[1][2]), ("0020_001", 134, 79))
    check("sb[2] (0020_002)", (sb[2][0].name, sb[2][1], sb[2][2]), ("0020_002", 213, 125))
    # clip immediately after a 54-frame gap should be offset by it
    after_gap = next(c for c in sb if c[0].name == "0090_003")
    check("0090_003 (after 54f gap)", after_gap[1], 1203)

    # audio offsets
    check("au[0] (010_0010_voice)", (au[0][0].name, au[0][1], au[0][2]),
          ("010_0010_voice", 0, 31))
    check("au[1] (010_0020_voice)", (au[1][0].name, au[1][1], au[1][2]),
          ("010_0020_voice", 31, 307))
    check("au[2] (010_0030_voice)", (au[2][0].name, au[2][1], au[2][2]),
          ("010_0030_voice", 338, 310))

    print(f"\n{'ALL PASSED' if not _failed else 'FAILED'}  ({_passed} passed, {_failed} failed)")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
