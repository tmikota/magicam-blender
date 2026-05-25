"""Pydantic v2 models for TVPaint ``clip_export.json`` files.

A single model set parses both the TVPaint 11 and TVPaint 12 export schemas.
The schemas differ only at clip/camera level; version-specific fields are
modelled as ``Optional`` so either file validates cleanly:

    - ``clip.markin`` / ``clip.markout``        v12 only (absent in v11)
    - ``clip.camera.profile``                   v11 only (dropped in v12)
    - ``clip.camera.lock-sizex`` / ``lock-sizey``  v12 only
    - camera keyframe ``frame`` / ``sizeX`` / ``sizeY``  v12 only

JSON uses hyphenated and camelCase keys (``image-count``, ``blending-mode``,
``sizeX`` ...); each maps to a snake_case attribute via a field alias.
``populate_by_name`` lets you construct models with either the alias or the
Python name, and ``model_dump(by_alias=True)`` reproduces the original keys.
"""

from __future__ import annotations

import json
from itertools import groupby
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr


def _format_ranges(frames: Iterable[int]) -> str:
    """Collapse a list of frame numbers into a "1,4-6,9" style string."""
    ordered = sorted(set(frames))
    parts: List[str] = []
    for _, group in groupby(enumerate(ordered), lambda pair: pair[1] - pair[0]):
        run = [value for _, value in group]
        parts.append(str(run[0]) if len(run) == 1 else f"{run[0]}-{run[-1]}")
    return ",".join(parts)


class _Base(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class Version(_Base):
    major: int
    minor: int


class ProjectFormat(_Base):
    extension: str


class ProjectCamera(_Base):
    """Render/output settings under ``project.camera`` (resolution, fps)."""

    width: int
    height: int
    field: int
    framerate: float
    pixel_aspect_ratio: float = Field(alias="pixelaspectratio")
    antialiasing: int


class BackgroundColor(_Base):
    red: int
    green: int
    blue: int


class MarkValue(_Base):
    """A ``markin`` / ``markout`` entry. v12 only."""

    status: bool
    value: int


class CameraKeyframe(_Base):
    """A single ``camera.points`` / ``camera.positions`` entry.

    v11 entries carry only x/y/angle/scale; v12 adds frame/sizeX/sizeY.
    """

    x: float
    y: float
    angle: float
    scale: float
    frame: Optional[int] = None
    size_x: Optional[float] = Field(default=None, alias="sizeX")
    size_y: Optional[float] = Field(default=None, alias="sizeY")


class ClipCamera(_Base):
    """The animated 2D camera under ``project.clip.camera``."""

    mode: int
    motion_blur: float = Field(alias="motion-blur")
    lock_all: bool = Field(alias="lock-all")
    lock_x: bool = Field(alias="lock-x")
    lock_y: bool = Field(alias="lock-y")
    lock_angle: bool = Field(alias="lock-angle")
    lock_scale: bool = Field(alias="lock-scale")
    profile: Optional[str] = None  # v11 only
    lock_sizex: Optional[bool] = Field(default=None, alias="lock-sizex")  # v12 only
    lock_sizey: Optional[bool] = Field(default=None, alias="lock-sizey")  # v12 only
    points: List[CameraKeyframe] = Field(default_factory=list)
    positions: List[CameraKeyframe] = Field(default_factory=list)


class LayerLink(_Base):
    """One exported image reference within a layer."""

    instance_index: int = Field(alias="instance-index")
    instance_name: str = Field(alias="instance-name")
    file: str
    images: List[int] = Field(default_factory=list)


class Layer(_Base):
    name: str
    visible: bool
    position: int
    opacity: int
    start: int
    end: int
    pre_behavior: int = Field(alias="pre-behavior")
    post_behavior: int = Field(alias="post-behavior")
    blending_mode: str = Field(alias="blending-mode")
    group: BackgroundColor
    link: List[LayerLink] = Field(default_factory=list)
    repeat: List[Any] = Field(default_factory=list)

    def image_files(self) -> List[str]:
        """Relative image paths (as exported) for every link on this layer."""
        return [lnk.file for lnk in self.link]

    def first_image_file(self, include_folder: bool = False) -> Optional[Union[str, List[str]]]:
        """The first link's file: bare filename, or split path parts if include_folder."""
        if not self.link:
            return None
        file = self.link[0].file
        return file.split("/") if include_folder else file.split("/")[-1]

    def image_paths(self, base_dir: Union[str, Path]) -> List[Path]:
        """Absolute image paths, resolving each link's file against base_dir."""
        base = Path(base_dir)
        return [base / lnk.file for lnk in self.link]

    def frame_indices(self) -> List[int]:
        """All image indices referenced by this layer's links (0-based, as exported)."""
        frames: List[int] = []
        for lnk in self.link:
            frames.extend(lnk.images)
        return frames

    def frame_range_string(self, one_based: bool = True) -> str:
        """Collapsed frame-range string for this layer (1-based by default)."""
        offset = 1 if one_based else 0
        return _format_ranges(f + offset for f in self.frame_indices())


class TVPaintClip(_Base):
    name: str
    width: int
    height: int
    dpi: int
    framerate: float
    pixel_aspect_ratio: float = Field(alias="pixelaspectratio")
    image_count: int = Field(alias="image-count")
    bg: BackgroundColor
    camera: ClipCamera
    layers: List[Layer] = Field(default_factory=list)
    markin: Optional[MarkValue] = None  # v12 only
    markout: Optional[MarkValue] = None  # v12 only

    def layer(self, name: str) -> Optional[Layer]:
        """Find a layer by exact name."""
        return next((lyr for lyr in self.layers if lyr.name == name), None)

    def layer_names(self, exclude: Optional[Iterable[str]] = None) -> List[str]:
        """Layer names, optionally dropping any name containing an exclude token."""
        names = [lyr.name for lyr in self.layers]
        for token in exclude or []:
            names = [n for n in names if token not in n]
        return names

    def frame_range_from_layers(self) -> Tuple[int, int]:
        """(min start, max end) across all layers, anchored at 0 like the original."""
        start, end = 0, 0
        for lyr in self.layers:
            start = min(start, lyr.start)
            end = max(end, lyr.end)
        return start, end

    def shot_frame_range(self) -> str:
        """The clip's mark range "markin-markout" (0-based). "0-0" if unmarked (v11)."""
        if self.markin and self.markout:
            return f"{self.markin.value}-{self.markout.value}"
        return "0-0"

    def clip_frame_range_string(self) -> str:
        """The clip's mark range as a 1-based "markin+1-markout+1" string."""
        if self.markin and self.markout:
            return f"{self.markin.value + 1}-{self.markout.value + 1}"
        return "1-1"


class TVPaintProject(_Base):
    format: ProjectFormat
    camera: ProjectCamera
    clip: TVPaintClip


class TVPaintExport(_Base):
    """Root of a TVPaint ``clip_export.json`` file."""

    version: Version
    project: TVPaintProject

    # Set by load_clip(); used to resolve relative image paths against the file's folder.
    _source_path: Optional[Path] = PrivateAttr(default=None)

    @property
    def clip(self) -> TVPaintClip:
        return self.project.clip

    @property
    def layers(self) -> List[Layer]:
        return self.project.clip.layers

    @property
    def source_path(self) -> Optional[Path]:
        return self._source_path

    @property
    def source_dir(self) -> Optional[Path]:
        """Folder the export was loaded from — the base for relative image paths."""
        return self._source_path.parent if self._source_path else None

    def layer(self, name: str) -> Optional[Layer]:
        return self.clip.layer(name)

    def layer_names(self, exclude: Optional[Iterable[str]] = None) -> List[str]:
        return self.clip.layer_names(exclude)

    def frame_range_from_layers(self) -> Tuple[int, int]:
        return self.clip.frame_range_from_layers()


def load_clip(path: Union[str, Path]) -> TVPaintExport:
    """Load and validate a TVPaint ``clip_export.json`` (v11 or v12)."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    export = TVPaintExport.model_validate(data)
    export._source_path = path
    return export
