"""
VERITAS dMRV — Perceptual-Hash Deduplication (FR-1.3)
======================================================

Detects the "Potemkin project" attack: a contractor submits the same stock
nursery photograph for many different parcels, or re-submits a photograph from
their own earlier report. EXIF cannot catch this because a legitimate-looking
photo legitimately carries its own coordinates.

pHash (perceptual hash) is the right tool: it is invariant to rescaling,
re-compression, mild colour and brightness adjustment, and minor crops, so a
resized re-upload still collides — which is exactly the class of abuse we
need to catch.

A plain pixel hash would not survive a resize, and would also produce false
positives on two genuinely different frames of the same static scene.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Iterable, Optional, Sequence

import imagehash
import numpy as np
from PIL import Image

#: Hamming distance at or below which two images are considered the same
#: photograph. 64-bit pHash: 0-5 near-duplicate, 6-11 likely duplicate,
#: 12+ distinct. 12 is the conservative quarantine threshold from FR-1.3.
PHASH_DUPLICATE_THRESHOLD = 12

#: Distance below which we additionally want a human to eyeball it.
PHASH_REVIEW_THRESHOLD = 8


class DedupVerdict(str, Enum):
    UNIQUE = "UNIQUE_ASSET"
    REVIEW_POSSIBLE_REUSE = "REVIEW_POSSIBLE_REUSE"
    QUARANTINE_DUPLICATE = "QUARANTINE_DUPLICATE"


@dataclass(frozen=True)
class DedupMatch:
    verdict: DedupVerdict
    phash: str
    min_distance_to_corpus: int
    nearest_match_asset_id: Optional[str]
    is_duplicate: bool
    corpus_size: int
    notes: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["verdict"] = self.verdict.value
        return d


def compute_phash(image: np.ndarray | Image.Image) -> str:
    """64-bit DCT perceptual hash, returned as a 16-char hex string."""
    pil = _as_pil(image)
    return str(imagehash.phash(pil))


def hamming_distance(phash_a: str, phash_b: str) -> int:
    """Bit distance between two 64-bit pHashes, in the range 0..64."""
    if len(phash_a) != len(phash_b):
        raise ValueError(
            f"phash length mismatch: {len(phash_a)} vs {len(phash_b)}"
        )
    return imagehash.hex_to_hash(phash_a) - imagehash.hex_to_hash(phash_b)


def _as_pil(image: np.ndarray | Image.Image) -> Image.Image:
    if isinstance(image, Image.Image):
        return image.convert("RGB")
    if image is None or getattr(image, "size", 0) == 0:
        raise ValueError("empty image")
    arr = np.asarray(image)
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr).convert("RGB")


class PhashCorpus:
    """In-memory pHash index over the project's ingested assets.

    Deliberately simple. At hackathon scale (hundreds to low thousands of
    assets) a linear scan over 64-bit XOR-and-popcount is microseconds, and a
    real ANN index would add a dependency without changing the answer. The
    interface is stable so an ANN backend can be dropped in later.
    """

    def __init__(self) -> None:
        self._entries: list = []  # (asset_id, phash, project_id)

    def __len__(self) -> int:
        return len(self._entries)

    def add(self, asset_id: str, phash: str, project_id: Optional[str] = None) -> None:
        self._entries.append((asset_id, phash, project_id))

    def add_image(
        self, asset_id: str, image: np.ndarray | Image.Image, project_id: Optional[str] = None
    ) -> str:
        ph = compute_phash(image)
        self.add(asset_id, ph, project_id)
        return ph

    def nearest(
        self, phash: str, same_project_only: bool = False, project_id: Optional[str] = None
    ) -> tuple:
        """Return (nearest_asset_id_or_None, min_distance)."""
        best_id, best_dist = None, 64
        for asset_id, other, proj in self._entries:
            if same_project_only and project_id is not None and proj != project_id:
                continue
            dist = hamming_distance(phash, other)
            if dist < best_dist:
                best_dist, best_id = dist, asset_id
        return best_id, best_dist

    def check(
        self,
        phash: str,
        asset_id: Optional[str] = None,
        project_id: Optional[str] = None,
        same_project_only: bool = False,
    ) -> DedupMatch:
        """Classify an incoming pHash against the corpus."""
        nearest_id, dist = self.nearest(
            phash, same_project_only=same_project_only, project_id=project_id
        )

        if nearest_id is None:
            return DedupMatch(
                verdict=DedupVerdict.UNIQUE,
                phash=phash,
                min_distance_to_corpus=64,
                nearest_match_asset_id=None,
                is_duplicate=False,
                corpus_size=len(self),
                notes="No prior assets in corpus; this is the first of its kind.",
            )

        # Re-submitting the identical asset is a different, weaker signal than
        # submitting a *different* asset id that collides with an existing one.
        is_self_resubmission = asset_id is not None and nearest_id == asset_id

        if dist <= PHASH_REVIEW_THRESHOLD:
            verdict = DedupVerdict.QUARANTINE_DUPLICATE
            is_dup = not is_self_resubmission
            notes = (
                f"pHash is {dist} bits from asset '{nearest_id}' "
                f"(threshold {PHASH_DUPLICATE_THRESHOLD}). Consistent with a "
                "recycled or re-submitted photograph."
            )
        elif dist <= PHASH_DUPLICATE_THRESHOLD:
            verdict = DedupVerdict.REVIEW_POSSIBLE_REUSE
            is_dup = False
            notes = (
                f"pHash is {dist} bits from asset '{nearest_id}', within the "
                f"{PHASH_DUPLICATE_THRESHOLD}-bit reuse band. A human should "
                "compare the two images before this is certified."
            )
        else:
            verdict = DedupVerdict.UNIQUE
            is_dup = False
            notes = f"Nearest corpus asset is {dist} bits away; treated as distinct."

        return DedupMatch(
            verdict=verdict,
            phash=phash,
            min_distance_to_corpus=int(dist),
            nearest_match_asset_id=nearest_id,
            is_duplicate=is_dup,
            corpus_size=len(self),
            notes=notes,
        )
