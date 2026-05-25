"""Pydantic model for a JSON HDRI library (converted from hdri.yaml).

JSON schema mirrors the source yaml::

    {"hdri": {"<Name>": {".exr": "/CGL-HDRI/hdri/Name.exr", ".tx": "...", "yrot": -100}}}

Relative paths (``/CGL-HDRI/...``) resolve against the JSON file's grandparent,
matching the library layout (``<root>/CGL-HDRI/hdri/Name.exr``). Thumbnails follow
the ``Name_thumb.png`` convention beside each HDRI. Stdlib + pydantic only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


class HdriEntry(_Base):
    name: str
    yrot: float = 0.0
    image_path: Optional[str] = None  # resolved absolute path to the .exr/.hdr
    thumb_path: Optional[str] = None  # resolved absolute path to Name_thumb.png
    formats: Dict[str, str] = {}      # ext -> relative path, as in the source


class HdriLibrary(_Base):
    entries: List[HdriEntry] = []

    def get(self, name: str) -> Optional[HdriEntry]:
        return next((e for e in self.entries if e.name == name), None)

    def names(self) -> List[str]:
        return [e.name for e in self.entries]


def load_hdri_library(json_path) -> HdriLibrary:
    """Load an HDRI library JSON and resolve absolute image/thumbnail paths."""
    json_path = Path(json_path)
    root = json_path.parent.parent  # /CGL-HDRI/... lives under here
    data = json.loads(json_path.read_text(encoding="utf-8"))

    entries: List[HdriEntry] = []
    for name, info in (data.get("hdri") or {}).items():
        formats = {k: v for k, v in info.items() if isinstance(k, str) and k.startswith(".")}
        yrot = float(info.get("yrot", 0) or 0)
        img_rel = (
            formats.get(".exr")
            or formats.get(".hdr")
            or next((v for k, v in formats.items() if k != ".tx"), None)
        )
        image_path = thumb_path = None
        if img_rel:
            image_path = str(root / img_rel.lstrip("/\\"))
            thumb_path = str(Path(image_path).with_name(f"{name}_thumb.png"))
        entries.append(
            HdriEntry(
                name=name,
                yrot=yrot,
                image_path=image_path,
                thumb_path=thumb_path,
                formats=formats,
            )
        )
    return HdriLibrary(entries=entries)
