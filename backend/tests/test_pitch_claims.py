"""The pitch must not outlive its evidence.

S7.7 re-cut the 180-second pitch to lead with rubric #3 and #5, and in doing so
removed three claims. Two were numbers whose provenance could not be traced; the
third was a regulatory-compliance claim about a validator that is not
implemented.

A pitch deck is the least guarded document in the repo. It is prose, it is
edited for rhythm, and nothing fails when a number in it drifts away from the
code. So the removals are pinned here.

THE THREE REMOVED CLAIMS

1. ``142 ms quarantine`` -- the only ``142`` in the codebase is
   ``baseline_canopy_pixels: 142100``, a PIXEL COUNT. The measured triage cost
   is ~1.11 ms. The slide had read a fixture field as a latency.
2. ``shadow diverges by 170.4 deg`` -- appears nowhere in the source, and ~180
   is the value for NO observed shadow rather than a real divergence. The
   tolerance is 12 degrees.
3. ``official EUDR Article 9 statutory dossier`` -- ``eudr_compliance_status``
   is a hardcoded literal and the M7 validator is on the cut list. A compliance
   product claiming compliance it has not checked is the exact failure it exists
   to catch.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PITCH = REPO / "docs" / "14-HACKATHON-PITCH-DECK-AND-PRESENTATION.md"
MATRIX = REPO / "docs" / "15-RUBRIC-TRACEABILITY.md"
LOAD_JSON = REPO / "docs" / "load-test.json"
BASELINE = REPO / "docs" / "LATENCY-BASELINE.md"

# The fenced timing block. Every line in it is a bracketed segment, not just the
# first -- an earlier version required all of them to start with "[00:00", so it
# matched nothing and reported "no timing architecture block" about a document
# that has one.
TIMING_BLOCK = re.compile(r"```\n((?:\[?\d\d:\d\d[^\n]*\n)+?)```")

# A retraction the presenter is entitled to make. Without these the spec flags
# the DISCLAIMER, which is the opposite of what it should do: slide 7 says out
# loud that an earlier version claimed EUDR compliance and that we do not, and
# that sentence is the most valuable thing in the pitch.
RETRACTION = re.compile(
    r"(claimed|earlier version|hadn'?t built|not implemented|never built|"
    r"does not|do not|is not|was a validator|on the cut list)",
    re.I,
)

EUDR_CLAIM = re.compile(
    r"(official|statutory|compliant)\s+EUDR|EUDR[^.]*\bcompliant\b", re.I
)


@pytest.fixture(scope="module")
def pitch() -> str:
    if not PITCH.exists():
        pytest.fail("docs/14 pitch deck is missing")
    return PITCH.read_text()


def spoken(text: str) -> list[str]:
    """The lines a presenter actually says: blockquotes inside list items.

    They are INDENTED, so matching ``line.startswith(">")`` found nothing and
    three specs passed against mutations they were meant to catch.
    """
    return [ln.strip() for ln in text.splitlines() if ln.lstrip().startswith(">")]


# --------------------------------------------------------------------------- #
# The extractor itself                                                        #
# --------------------------------------------------------------------------- #


def test_the_spoken_line_extractor_finds_the_scripts(pitch: str) -> None:
    """Guards the guard.

    If this returned nothing, every claim spec below would be vacuously true --
    which is the failure mode this repo keeps finding, and the reason a spec that
    "passes" is not evidence that the rule holds.
    """
    lines = spoken(pitch)
    assert len(lines) > 20, f"only {len(lines)} spoken lines; the extractor is broken"
    assert any("Let" in ln for ln in lines), "no speaker script found"


# --------------------------------------------------------------------------- #
# The removed claims                                                          #
# --------------------------------------------------------------------------- #


def test_no_spoken_142ms_latency(pitch: str) -> None:
    for ln in spoken(pitch):
        assert not re.search(r"\b142\s*ms", ln, re.I), (
            f"the pitch speaks a 142 ms latency: {ln!r}. The only 142 in the "
            "source is baseline_canopy_pixels=142100, a pixel count. The "
            "measured triage cost is ~1.11 ms."
        )


def test_no_spoken_170_degree_divergence(pitch: str) -> None:
    for ln in spoken(pitch):
        assert "170.4" not in ln, (
            f"the pitch speaks a 170.4 degree divergence: {ln!r}. That number is "
            "in no source file, and ~180 is what you get with no observed shadow "
            "at all. The tolerance is 12 degrees."
        )


def test_no_eudr_compliance_assertion(pitch: str) -> None:
    """Scanned sentence by sentence, so a retraction is allowed and an assertion
    in the same script is not. A line-level check flagged slide 7's own
    disclaimer, making the useful half of the correction indistinguishable from
    the mistake it corrects."""
    offenders = []
    for ln in spoken(pitch):
        for sentence in re.split(r"(?<=[.!?])\s+", ln):
            if EUDR_CLAIM.search(sentence) and not RETRACTION.search(sentence):
                offenders.append(sentence.strip())
    assert not offenders, (
        f"the pitch asserts EUDR compliance: {offenders}. The M7 Article 9 "
        "validator is on the cut list and eudr_compliance_status is a hardcoded "
        "literal."
    )


def test_the_disclaimer_is_still_spoken(pitch: str) -> None:
    """Without this, the check above could be satisfied by deleting slide 7's
    retraction entirely -- which is what a well-meaning editor does to make a
    spec pass."""
    lines = " ".join(spoken(pitch))
    assert "not implemented" in lines, (
        "the spoken script no longer says the Article 9 validator is missing"
    )
    assert "hadn't built" in lines or "hadn’t built" in lines, (
        "the retraction of the earlier compliance claim is gone"
    )


def test_the_dossier_format_claim_survives(pitch: str) -> None:
    """Removing the compliance claim must not remove the real contribution.

    The dossier genuinely does emit coordinate vertices as decimal strings so
    declared precision survives the wire, which a JSON number cannot. Dropping
    that alongside the overclaim would be over-correcting.
    """
    assert "decimal string" in pitch.lower()


# --------------------------------------------------------------------------- #
# The re-cut actually happened                                                #
# --------------------------------------------------------------------------- #


def test_pitch_leads_with_the_demo_not_the_market_hook(pitch: str) -> None:
    """7.7: lead with rubric #3 and #5, not the carbon-market hook.

    The first timing segment must be the live demonstration. A re-cut that
    leaves the hook first has not been done, whatever the version number claims.
    """
    match = TIMING_BLOCK.search(pitch)
    assert match, "no timing architecture block found"
    segments = re.findall(r"\[\d\d:\d\d\s*-\s*\d\d:\d\d\][^\n]*", match.group(0))
    assert segments, f"no timing segments in {match.group(0)!r}"
    first = segments[0]
    assert "LIVE" in first, f"the pitch still opens on slides: {first!r}"
    assert "rubric #3" in first, f"slide 1 must be rubric #3: {first!r}"


def test_timing_adds_up_to_180_seconds(pitch: str) -> None:
    """An architecture that does not sum to 180 is not an architecture."""
    match = TIMING_BLOCK.search(pitch)
    assert match, "no timing block"
    total = 0
    for line in match.group(1).strip().splitlines():
        m = re.search(r"\[(\d\d):(\d\d)\s*-\s*(\d\d):(\d\d)\]", line)
        assert m, f"unparseable timing line: {line!r}"
        start = int(m.group(1)) * 60 + int(m.group(2))
        end = int(m.group(3)) * 60 + int(m.group(4))
        assert end > start, f"non-increasing segment: {line!r}"
        total += end - start
    assert total == 180, f"the pitch sums to {total}s, not 180s"


def test_claims_audit_exists(pitch: str) -> None:
    """Every figure must be classifiable: measured, claimed, or removed."""
    assert "Claims audit" in pitch
    for classification in ("measured", "fixture value", "REMOVED"):
        assert classification in pitch, f"no '{classification}' row in the audit"


# --------------------------------------------------------------------------- #
# The quoted figures must be current                                          #
# --------------------------------------------------------------------------- #


def test_throughput_quote_matches_the_load_test_report(pitch: str) -> None:
    """Checked between the AUDIT TABLE and the SPOKEN SCRIPT, not for presence.

    Checking presence was the first version and it passed against a mutation
    that rewrote the spoken figure, because the same number also appears in the
    claims-audit table. A test satisfied by a number appearing *anywhere* cannot
    detect the document contradicting itself.
    """
    rate_m = re.search(r'"assets_per_second":\s*([\d.]+)', LOAD_JSON.read_text())
    assert rate_m, "load-test.json has no throughput"
    rate = f"{float(rate_m.group(1)):.2f} assets"

    said = " ".join(spoken(pitch))
    assert rate in said, (
        f"the spoken script does not quote the current throughput ({rate}/s) "
        "from docs/load-test.json"
    )

    row = re.search(r"\| 500 assets[^\n]*", pitch)
    assert row, "no throughput row in the claims audit"
    assert rate in row.group(0), (
        f"the claims audit and the spoken script disagree: {row.group(0)!r}"
    )


def test_solar_quote_matches_the_latency_baseline(pitch: str) -> None:
    said = " ".join(spoken(pitch))
    m = re.search(
        r"Solar ephemeris \+ shadow coherence \| ([\d.]+) ms", BASELINE.read_text()
    )
    assert m, "LATENCY-BASELINE.md has no solar median"
    ms = f"{float(m.group(1)):.2f} ms"
    assert ms in said, (
        f"the spoken script quotes a rounded or stale solar figure; the report "
        f"says {ms}"
    )


# --------------------------------------------------------------------------- #
# The generated matrix                                                        #
# --------------------------------------------------------------------------- #


def test_rubric_matrix_covers_every_bullet() -> None:
    if not MATRIX.exists():
        pytest.fail(
            "docs/15-RUBRIC-TRACEABILITY.md is missing; run `make rubric-matrix`"
        )
    text = MATRIX.read_text()
    for bullet in ("intro", "1", "2", "3", "4", "5", "6"):
        assert f"| **{bullet}** |" in text, f"rubric {bullet} is missing from the matrix"


def test_rubric_matrix_states_its_own_limits() -> None:
    text = MATRIX.read_text()
    assert "Generated by" in text
    assert "Known gaps in this matrix" in text
    assert "f_pdf" in text, "the plan-gated PDF gap is not recorded"
    assert "webhook" in text.lower(), "the unconfirmed webhook gap is not recorded"
    assert "time-to-reach" in text, "the timestamps are not qualified as a floor"


def test_matrix_demo_timestamps_were_measured() -> None:
    tl = json.loads((REPO / "docs" / "demo-timeline.json").read_text())
    assert len(tl["surfaces"]) >= 7
    for s in tl["surfaces"]:
        assert isinstance(s["offset_s"], (int, float))
        assert s["offset_s"] >= 0
    assert tl["walkthrough_seconds"] < 180, (
        "the walkthrough does not fit inside the pitch it is timing"
    )
