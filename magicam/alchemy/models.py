"""Pydantic read model for Alchemy edit timelines (``scene_*_timeline.json``).

A timeline is two sequential tracks — a storyboard (video) track and an audio
track — each a list of clips (and Gaps). Clip ``clip_range`` times are relative
(every clip starts at 0), so a clip's absolute position on the timeline is the
cumulative sum of the durations before it, with Gaps advancing the cursor.

Pure data model: no ``bpy`` and no ``alc`` dependency, so it validates anywhere
pydantic is installed. Path resolution (media_url -> disk) lives in the Blender
translator, which may use ``alc.path``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator, List, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


class RationalTime(_Base):
    value: float
    rate: float

    @property
    def frames(self) -> int:
        return int(round(self.value))

    @property
    def seconds(self) -> float:
        return self.value / self.rate if self.rate else 0.0


class TimeRange(_Base):
    start_time: RationalTime
    duration: RationalTime


class TimelineClip(_Base):
    kind: str
    name: str
    clip_range: TimeRange
    block_id: Optional[str] = None
    media_url: Optional[str] = None
    manifest_relative_path: Optional[str] = None
    thumbnail_url: Optional[str] = None

    @property
    def duration_frames(self) -> int:
        return self.clip_range.duration.frames

    @property
    def is_gap(self) -> bool:
        return self.kind == "Gap"


# (clip, absolute_start_frame, duration_frames)
ClipOffset = Tuple[TimelineClip, int, int]


class Track(_Base):
    name: str
    kind: str
    children: List[TimelineClip] = []

    def clips_with_offsets(self, start: int = 0) -> Iterator[ClipOffset]:
        """Yield each clip with its absolute start frame; Gaps advance the cursor."""
        cursor = start
        for clip in self.children:
            duration = clip.duration_frames
            yield clip, cursor, duration
            cursor += duration

    def total_frames(self) -> int:
        return sum(clip.duration_frames for clip in self.children)


class Timeline(_Base):
    name: str
    scene_id: Optional[str] = None
    global_start_time: Optional[Any] = None
    audio_track: Optional[Track] = None
    storyboard_track: Optional[Track] = None

    def storyboard_clips(self) -> Iterator[ClipOffset]:
        """Image clips on the storyboard track with absolute offsets (Gaps skipped)."""
        if not self.storyboard_track:
            return
        for clip, start, dur in self.storyboard_track.clips_with_offsets():
            if not clip.is_gap:
                yield clip, start, dur

    def audio_clips(self) -> Iterator[ClipOffset]:
        """Clips on the audio track with absolute offsets (Gaps skipped)."""
        if not self.audio_track:
            return
        for clip, start, dur in self.audio_track.clips_with_offsets():
            if not clip.is_gap:
                yield clip, start, dur

    def total_frames(self) -> int:
        tracks = [t for t in (self.audio_track, self.storyboard_track) if t]
        return max((t.total_frames() for t in tracks), default=0)


def load_timeline(path: Union[str, Path]) -> Timeline:
    """Load and validate an Alchemy ``scene_*_timeline.json``.

    Alchemy saves the timeline nested under the scene manifest (a top-level
    ``"timeline"`` key alongside scene fields like ``scene_id``/``heading``), so unwrap
    it — carrying ``scene_id`` down from the parent — before validating. Falls back to
    treating ``data`` as the timeline itself if there's no wrapper. Mirrors Alchemy's
    own ``SceneTimeline.load_manifest``. Unknown fields (e.g. ``shot_track``,
    ``shots_locked``, clip ``shot_type``) are ignored via the model's ``extra="ignore"``.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "timeline" in data and isinstance(data["timeline"], dict):
        scene_id = data.get("scene_id")
        data = data["timeline"]
        if scene_id and not data.get("scene_id"):
            data["scene_id"] = scene_id
    return Timeline.model_validate(data)
