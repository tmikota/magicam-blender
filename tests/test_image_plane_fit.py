"""The aspect decision behind letterbox/pillarbox, tested without Blender.

``fit_uv_scale`` is deliberately bpy-free so the maths that decides whether a board
gets bars top-and-bottom or left-and-right can be pinned here. The node wiring it
feeds is verified in Blender.
"""

import importlib.util
from pathlib import Path

import pytest

# Import the module's pure-python half without importing bpy: load the source and
# exec only the function under test. (magicam.blender.image_plane imports bpy at
# module level, which is unavailable outside Blender.)
_SRC = (
    Path(__file__).resolve().parents[1] / "magicam" / "blender" / "image_plane.py"
).read_text(encoding="utf-8")
_ns: dict = {}
_start = _SRC.index("def fit_uv_scale")
_end = _SRC.index("def _plane_aspect")
exec(compile(_SRC[_start:_end], "image_plane.py", "exec"), _ns)
fit_uv_scale = _ns["fit_uv_scale"]

WIDESCREEN = 16 / 9


def test_matching_aspect_is_left_alone():
    """A board already the plane's shape must not be touched — the common case."""
    assert fit_uv_scale(WIDESCREEN, WIDESCREEN) == (1.0, 1.0)


def test_wider_image_gets_bars_top_and_bottom():
    """A 2.39:1 board on a 16:9 plane fits to WIDTH: V scales, U does not."""
    sx, sy = fit_uv_scale(2.39, WIDESCREEN)
    assert sx == 1.0
    assert sy == pytest.approx(2.39 / WIDESCREEN)
    assert sy > 1.0  # showing more than the image vertically = transparent bars


def test_taller_image_gets_bars_left_and_right():
    """A 4:3 board on a 16:9 plane fits to HEIGHT: U scales, V does not."""
    sx, sy = fit_uv_scale(4 / 3, WIDESCREEN)
    assert sy == 1.0
    assert sx == pytest.approx(WIDESCREEN / (4 / 3))
    assert sx > 1.0


def test_only_one_axis_ever_scales():
    """The whole point: the image is never distorted, only inset."""
    for image_aspect in (0.5, 1.0, 4 / 3, 1.85, 2.39, 3.0):
        sx, sy = fit_uv_scale(image_aspect, WIDESCREEN)
        assert sx == 1.0 or sy == 1.0


def test_scale_is_the_ratio_of_aspects_either_way():
    """Bars are proportional to how far off the aspect is, in both directions."""
    # A 4:3 image is as far from 16:9 as a 16:9 image is from a 4:3 plane.
    sx, _ = fit_uv_scale(4 / 3, WIDESCREEN)
    _, sy = fit_uv_scale(WIDESCREEN, 4 / 3)
    assert sx == pytest.approx(sy)


def test_portrait_image_on_a_landscape_plane():
    """A 9:16 vertical board pillarboxes hard rather than stretching to fill."""
    sx, sy = fit_uv_scale(9 / 16, WIDESCREEN)
    assert sy == 1.0
    assert sx == pytest.approx(WIDESCREEN / (9 / 16))


@pytest.mark.parametrize(
    "image_aspect,plane_aspect",
    [(0, WIDESCREEN), (WIDESCREEN, 0), (-1, WIDESCREEN), (WIDESCREEN, -1)],
)
def test_degenerate_aspects_are_a_no_op(image_aspect, plane_aspect):
    """A zero-size image or plane must not raise or produce a division blow-up."""
    assert fit_uv_scale(image_aspect, plane_aspect) == (1.0, 1.0)
