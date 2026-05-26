"""Free-function query API over the TVPaint models.

Mirrors the names of the legacy ``cgl.plugins.tvpaint.query`` module so existing
callers port over with minimal churn, but each function delegates to the pydantic
model and accepts a path, a parsed dict, or an already-loaded ``TVPaintExport``.

The pure pipeline/filesystem helpers from the legacy module (export folder paths,
``wait_until_export_is_done`` ...) are intentionally not ported here — they are
environment utilities, not clip-data queries.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Union

from .models import Layer, TVPaintExport, load_clip

Source = Union[str, Path, dict, TVPaintExport]


def _as_export(source: Source) -> TVPaintExport:
    if isinstance(source, TVPaintExport):
        return source
    if isinstance(source, dict):
        return TVPaintExport.model_validate(source)
    return load_clip(source)


def _base_dir(source: Source, export: TVPaintExport) -> Optional[Path]:
    if isinstance(source, (str, Path)):
        return Path(source).parent
    return export.source_dir


def tvp_data(source: Source) -> TVPaintExport:
    """Load (or pass through) a TVPaint export as a validated model."""
    return _as_export(source)


def layers(source: Source) -> List[Layer]:
    return _as_export(source).clip.layers


def layer_names(source: Source, filter: Optional[Iterable[str]] = None) -> List[str]:
    return _as_export(source).clip.layer_names(filter)


def get_first_image_name(
    source: Source, layer_name: str, include_folder: bool = False
) -> Optional[Union[str, List[str]]]:
    layer = _as_export(source).clip.layer(layer_name)
    return layer.first_image_file(include_folder) if layer else None


def frame_range_from_layers(source: Source) -> Tuple[int, int]:
    return _as_export(source).clip.frame_range_from_layers()


def shot_frame_range(source: Source) -> str:
    return _as_export(source).clip.shot_frame_range()


def layer_frame_range(source: Source, layer_name: Optional[str] = None) -> str:
    """1-based frame range. Whole-clip mark range when layer_name is None."""
    clip = _as_export(source).clip
    if layer_name is None:
        return clip.clip_frame_range_string()
    layer = clip.layer(layer_name)
    if layer is None:
        raise KeyError(f"Layer '{layer_name}' not found")
    return layer.frame_range_string(one_based=True)


def layer_images(source: Source, layer_name: str) -> List[str]:
    """Absolute image paths for a layer, resolved against the export's folder."""
    export = _as_export(source)
    layer = export.clip.layer(layer_name)
    if layer is None:
        raise KeyError(f"Layer '{layer_name}' not found")
    base = _base_dir(source, export)
    if base is None:
        raise ValueError(
            "Cannot resolve image paths: pass a file path, or load via load_clip()"
        )
    return [str(p) for p in layer.image_paths(base)]
