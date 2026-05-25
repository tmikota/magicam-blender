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
from pathlib import Path
from typing import Any, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


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


class TVPaintProject(_Base):
    format: ProjectFormat
    camera: ProjectCamera
    clip: TVPaintClip


class TVPaintExport(_Base):
    """Root of a TVPaint ``clip_export.json`` file."""

    version: Version
    project: TVPaintProject

    @property
    def clip(self) -> TVPaintClip:
        return self.project.clip

    @property
    def layers(self) -> List[Layer]:
        return self.project.clip.layers


def load_clip(path: Union[str, Path]) -> TVPaintExport:
    """Load and validate a TVPaint ``clip_export.json`` (v11 or v12)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return TVPaintExport.model_validate(data)
