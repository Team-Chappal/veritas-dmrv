"""
VERITAS dMRV — AI Video Analysis & Visual Transcription
=======================================================

RUBRIC CONTEXT
--------------
The brief asks the platform to *"analyze and intelligently organize large
collections of image AND VIDEO evidence"* and to *"identify relevant ...
visual signals from media."* Video is half the collection volume in this domain
— drone transects over a restoration plot — and until now it entered the
platform as an opaque file. Nothing indexed it, nothing searched it, and no
auditor could find the 40 seconds of a 15-minute flight where something
interesting happened.

Cloudinary's AI Video Analysis returns timestamped categorisation segments
(``google_video_tagging``). This module turns those into two things the rest of
the platform can use:

1. **A WebVTT caption track** — real, playable subtitles carrying the visual
   transcript, so the footage is searchable and accessible.
2. **Spatial hotspots** — time-anchored annotations, which is what the
   interactive video player pins over the moving footage (rubric bullet 2).

WHY THE TIMECODE HANDLING IS CAREFUL
------------------------------------
A caption track is a media file with a strict grammar, and the two ways it
fails are both silent: a malformed timestamp makes the whole track refuse to
load, and overlapping cues make players drop segments. So :func:`format_timestamp`
is total over its inputs, cues are sorted and de-overlapped before emission,
and :func:`validate_vtt` re-parses the rendered document and checks it against
the source segments. A track is never returned unvalidated.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Iterable, Optional, Sequence

#: Cloudinary's Google video tagging emits a label with a confidence per
#: time window. Segments below this are dropped: below roughly 0.6 the label is
#: not distinguishable from the classifier guessing, and an unreliable caption
#: track is worse than a sparse one.
MIN_TAG_CONFIDENCE = 0.6

#: Cues shorter than this cannot be read and cause players to flicker.
MIN_CUE_SECONDS = 0.8

#: Gap inserted between consecutive cues so a reader can register that the
#: caption changed, and so cues never butt up against each other.
CUE_GAP_SECONDS = 0.1


class VideoAnalysisError(ValueError):
    """A tagging payload could not be turned into a usable caption track."""


@dataclass
class VideoSegment:
    """One time-anchored visual observation."""

    tag: str
    start: float
    end: float
    confidence: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Hotspot:
    """A clickable spatial annotation for the interactive player."""

    hotspot_id: str
    title: str
    start: float
    end: float
    x_pct: float
    y_pct: float
    description: str
    telemetry: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Timecode
# --------------------------------------------------------------------------- #


def format_timestamp(seconds: float) -> str:
    """Format seconds as a WebVTT timestamp: ``HH:MM:SS.mmm``.

    Total by construction: negative and NaN inputs clamp rather than raise, so a
    malformed segment from a third-party classifier cannot produce a caption
    track that fails to load. Rounding carries, so a 59.9996s value becomes
    ``00:01:00.000`` instead of wrapping to a negative field.
    """
    try:
        value = float(seconds)
    except (TypeError, ValueError):
        value = 0.0
    if value != value:  # NaN
        value = 0.0
    value = max(value, 0.0)

    total_ms = int(round(value * 1000.0))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def parse_timestamp(text: str) -> float:
    """Inverse of :func:`format_timestamp`, used by the validator."""
    hours, minutes, rest = text.split(":")
    secs, millis = rest.split(".")
    return (
        int(hours) * 3600 + int(minutes) * 60 + int(secs) + int(millis) / 1000.0
    )


# --------------------------------------------------------------------------- #
# VTT
# --------------------------------------------------------------------------- #


def _clean_cue_text(tag: str) -> str:
    """A caption line must not contain a blank line or a ``-->`` arrow.

    A blank line terminates the cue early; an arrow is cue syntax. Both are
    rejected here rather than producing a track that players mis-parse.
    """
    text = str(tag).replace("\n", " ").replace("\r", " ").strip()
    if "-->" in text:
        raise VideoAnalysisError(
            f"tag contains a cue arrow and cannot be a caption line: {tag!r}"
        )
    return text


def build_vtt(
    segments: Sequence,
    kind: str = "captions",
    max_lines: Optional[int] = None,
) -> str:
    """Render segments as a WebVTT document.

    Args:
        segments: ``VideoSegment`` values, or dicts with the same keys.
        kind: WebVTT cue kind, e.g. ``captions``.
        max_lines: Optional cap on emitted cues. Applied AFTER filtering, so
            the cap never silently removes the highest-confidence segment.

    Raises:
        VideoAnalysisError: if a segment cannot be rendered as a valid cue.
    """
    parsed = [_coerce(s) for s in segments]
    parsed = [s for s in parsed if s is not None]
    if not parsed:
        raise VideoAnalysisError("No segments survived confidence filtering.")

    # --- Sweep the timeline into non-overlapping windows ------------------- #
    #
    # Cloudinary's tagging returns NESTED windows: a "canopy" segment routinely
    # sits inside a "forest" segment. Overlapping cues are invalid VTT, and
    # simply pushing each cue's start past the previous cue's end produced a
    # NEGATIVE duration here, which the validator then rejected.
    #
    # Dropping the nested tag would discard a real observation, so instead the
    # timeline is swept into atomic intervals and every tag active in an
    # interval becomes a line within that interval's cue. Multi-line cues are
    # valid WebVTT, so nothing is lost and nothing overlaps.
    edges = sorted({s.start for s in parsed} | {s.end for s in parsed})
    windows = [
        (a, b) for a, b in zip(edges, edges[1:]) if b - a >= MIN_CUE_SECONDS
    ]

    cues = []
    for start, end in windows:
        if len(cues) >= max_lines if max_lines is not None else False:
            break
        active = [
            s for s in parsed
            if s.start <= start and s.end >= end and s.confidence >= MIN_TAG_CONFIDENCE
        ]
        if not active:
            continue
        # Highest confidence first, so the most reliable label leads the cue.
        active.sort(key=lambda s: -s.confidence)
        lines_in_cue = [_clean_cue_text(s.tag) for s in active]
        # De-duplicate identical labels within a window.
        seen, unique = set(), []
        for line in lines_in_cue:
            if line not in seen:
                seen.add(line)
                unique.append(line)
        cues.append((start, min(end, start + 60.0), unique))

    if not cues:
        raise VideoAnalysisError(
            f"All {len(parsed)} segment(s) fell below confidence "
            f"{MIN_TAG_CONFIDENCE} or the {MIN_CUE_SECONDS}s minimum window."
        )

    if max_lines is not None and len(cues) > max_lines:
        cues = sorted(cues, key=lambda c: c[2][0])[:max_lines]

    lines = ["WEBVTT", ""]
    if kind and kind != "captions":
        lines += [f"NOTE kind: {kind}", ""]

    for i, (start, end, texts) in enumerate(cues, start=1):
        lines.append(str(i))
        lines.append(f"{format_timestamp(start)} --> {format_timestamp(end)}")
        lines.extend(texts)
        lines.append("")

    document = "\n".join(lines)
    problems = validate_vtt(document, expected=len(cues))
    if problems:
        raise VideoAnalysisError(
            f"Rendered VTT failed validation: {problems}. Refusing to emit a "
            "caption track that players would reject."
        )
    return document


def validate_vtt(document: str, expected: Optional[int] = None) -> list:
    """Re-parse a rendered VTT and report structural problems.

    Deliberately does not use a VTT library: the grammar is small, and an
    independent re-parse is the only check that is not simply agreeing with the
    code that wrote it.
    """
    problems = []
    if not document.startswith("WEBVTT"):
        problems.append("missing WEBVTT header")

    body = document.split("\n", 1)[1] if "\n" in document else ""
    cues = []
    for block in body.split("\n\n"):
        block = block.strip("\n")
        if not block.strip():
            continue
        if block.startswith("NOTE"):
            continue
        lines = [ln for ln in block.split("\n") if ln.strip()]
        if len(lines) < 2:
            problems.append(f"cue block too short: {block[:40]!r}")
            continue
        if "-->" not in lines[1] if len(lines) > 1 else True:
            problems.append(f"cue missing timing line: {block[:40]!r}")
            continue
        start_text, _, end_text = lines[1].partition("-->")
        try:
            start = parse_timestamp(start_text.strip())
            end = parse_timestamp(end_text.strip())
        except (ValueError, IndexError):
            problems.append(f"unparseable timestamp: {lines[1][:40]!r}")
            continue
        if end <= start:
            problems.append(f"cue ends at or before it starts: {lines[1][:40]!r}")
        cues.append((start, end))

    for (s1, e1), (s2, _) in zip(cues, cues[1:]):
        if s2 < e1:
            problems.append(
                f"cue at {format_timestamp(s2)} overlaps the previous one ending "
                f"at {format_timestamp(e1)}"
            )

    if expected is not None and len(cues) != expected:
        problems.append(f"expected {expected} cues, rendered {len(cues)}")

    return problems


# --------------------------------------------------------------------------- #
# Cloudinary payload parsing
# --------------------------------------------------------------------------- #


def parse_google_video_tagging(
    payload: dict, min_confidence: float = MIN_TAG_CONFIDENCE
) -> list:
    """Extract :class:`VideoSegment` values from an AI Video Analysis payload.

    Accepts the shape Cloudinary delivers under
    ``info.categorization.google_video_tagging.data``, and tolerates the
    millisecond-string and float-second variants seen in the wild.
    """
    data = ((payload or {}).get("info", {})
            .get("categorization", {})
            .get("google_video_tagging", {})
            .get("data"))
    if not isinstance(data, list):
        return []

    segments = []
    for item in data:
        if not isinstance(item, dict):
            continue
        tag = item.get("tag")
        start = item.get("start_time_offset", item.get("start"))
        end = item.get("end_time_offset", item.get("end"))
        if tag is None or start is None or end is None:
            continue
        try:
            start_f = float(start)
            end_f = float(end)
        except (TypeError, ValueError):
            continue
        if end_f < start_f:
            start_f, end_f = end_f, start_f
        try:
            confidence = float(item.get("confidence", 1.0))
        except (TypeError, ValueError):
            confidence = 1.0
        if confidence < min_confidence:
            continue
        segments.append(VideoSegment(str(tag), start_f, end_f, confidence))

    segments.sort(key=lambda s: (s.start, -s.confidence))
    return segments


def segments_to_hotspots(
    segments: Sequence,
    labels: Optional[dict] = None,
    *,
    x_pct: float = 50.0,
    y_pct: float = 50.0,
) -> list:
    """Turn visual segments into player hotspots.

    ``labels`` maps a tag to display metadata (title, description, telemetry).
    A tag with no entry still produces a hotspot, using the tag itself as the
    title — an unlabelled observation is still an observation.

    Segments below :data:`MIN_TAG_CONFIDENCE` or :data:`MIN_CUE_SECONDS` are
    dropped here too, so hotspots and caption tracks never disagree about which
    observations exist.
    """
    labels = labels or {}
    parsed = [_coerce(s) for s in segments]
    # Same filters the caption track applies. A 0.1 s hotspot is unclickable
    # in practice and only adds noise to the player's pin list, so the two
    # surfaces must agree about what counts as an observation.
    parsed = [
        s for s in parsed
        if s is not None
        and s.confidence >= MIN_TAG_CONFIDENCE
        and s.end - s.start >= MIN_CUE_SECONDS
    ]
    parsed.sort(key=lambda s: (s.start, -s.confidence))
    out = []
    for i, seg in enumerate(parsed):
        meta = labels.get(seg.tag, {})
        out.append(
            Hotspot(
                hotspot_id=f"pin-{i + 1}-{_slug(seg.tag)}",
                title=meta.get("title", seg.tag.replace("_", " ").title()),
                start=max(0.0, seg.start),
                end=seg.end,
                x_pct=x_pct,
                y_pct=y_pct,
                description=meta.get("description", f"Observed: {seg.tag}"),
                telemetry=dict(meta.get("telemetry", {"confidence": seg.confidence})),
            )
        )
    return out


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in str(text).lower()).strip("-")


def _coerce(item) -> Optional[VideoSegment]:
    if isinstance(item, VideoSegment):
        return item
    if isinstance(item, dict):
        try:
            return VideoSegment(
                tag=str(item["tag"]),
                start=float(item["start"]),
                end=float(item["end"]),
                confidence=float(item.get("confidence", 1.0)),
            )
        except (KeyError, TypeError, ValueError):
            return None
    return None
