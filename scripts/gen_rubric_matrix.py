"""S7.6 — generate docs/15-RUBRIC-TRACEABILITY.md from an actual run.

The matrix is GENERATED, not written by hand. A traceability matrix whose
component names, test names and demo timestamps were typed from memory drifts
from the code within a commit or two, and a stale matrix is worse than none,
because it looks authoritative.

So the demo timestamps come from ``frontend/e2e/rubric-walkthrough.spec.ts``,
which drives the real page and records when each graded surface becomes visible,
and the component and test references are verified against the tree before they
are written. If a component is renamed, this script fails rather than emitting a
matrix that points at nothing.

Usage:
    PYTHONPATH=backend backend/.venv/bin/python scripts/gen_rubric_matrix.py
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FRONTEND = REPO / "frontend"
TIMELINE = REPO / "docs" / "demo-timeline.json"
OUT = REPO / "docs" / "15-RUBRIC-TRACEABILITY.md"

# bullet -> (component file, frontend spec, backend spec, backend routes, demo surface)
MATRIX = [
    {
        "bullet": "intro",
        "requirement": "Timeline: project → epoch → asset, coverage gaps visible",
        "component": "frontend/components/ProjectTimeline.tsx",
        "fe_spec": "frontend/e2e/timeline.spec.ts",
        "be_spec": "backend/tests/test_integration.py",
        "routes": "/v1/projects/{id}/timeline",
        "surface": "project-timeline",
        "note": (
            "Gaps are shown as gaps. An epoch with no assets is rendered empty and "
            "labelled, rather than omitted, so an absence reads as an absence."
        ),
    },
    {
        "bullet": "1",
        "requirement": "Analyze and organize large collections",
        "component": "frontend/components/PortfolioGrid.tsx",
        "fe_spec": "frontend/e2e/portfolio.spec.ts",
        "be_spec": "backend/tests/test_enrichment.py",
        "routes": "/v1/assets",
        "surface": "portfolio-grid",
        "note": (
            "Grouped by project and epoch with counts, not a flat list of 500 rows. "
            "Scale measured separately: 500 assets at 1.07 assets/s "
            "(docs/LOAD-TEST.md)."
        ),
    },
    {
        "bullet": "2",
        "requirement": "Identify projects, locations and visual signals",
        "component": "frontend/components/HotspotVideoPlayer.tsx",
        "fe_spec": "frontend/e2e/hotspot-player.spec.ts",
        "be_spec": "backend/tests/test_video_webhooks.py",
        "routes": "/v1/media/analyse",
        "surface": "hotspot-player",
        "note": (
            "Auto-tagged hotspots over the clip, mirrored as text so nothing needs "
            "to be seen. Clicking a hotspot SEEKS the video. Markers are labelled "
            "claims, not measurements."
        ),
    },
    {
        "bullet": "3",
        "requirement": "Before-and-after comparison",
        "component": "frontend/components/ProofOfImpactStudio.tsx",
        "fe_spec": "frontend/e2e/impact.spec.ts",
        "be_spec": "backend/tests/test_vision.py",
        "routes": "/v1/cv/align-and-diff",
        "surface": "impact-studio",
        "note": (
            "Split slider with the measured canopy delta and the inlier-ratio "
            "badge. The inlier ratio is shown because a Δ computed from a "
            "degraded registration is not a measurement."
        ),
    },
    {
        "bullet": "4",
        "requirement": "Reports, summaries and campaign content",
        "component": "frontend/components/CampaignStudio.tsx",
        "fe_spec": "frontend/e2e/campaign.spec.ts",
        "be_spec": "backend/tests/test_report_service.py",
        "routes": "/v1/audit/dossier/{id}",
        "surface": "campaign-studio",
        "note": (
            "9:16 reel, certificate and dossier. The PDF is labelled plan-gated: "
            "f_pdf is a paid-plan transformation and the free tier returns 401."
        ),
    },
    {
        "bullet": "5",
        "requirement": "AI metadata, tagging, semantic discovery",
        "component": "frontend/components/SemanticSearch.tsx",
        "fe_spec": "frontend/e2e/search.spec.ts",
        "be_spec": "backend/tests/test_integration.py",
        "routes": "/v1/search",
        "surface": "semantic-search",
        "note": (
            "BM25 and cosine over the Search API — LEXICAL, not neural, and the "
            "panel says so. The empty-result path names the fields searched, "
            "because a search box that quietly returns nothing is "
            "indistinguishable from a broken one."
        ),
    },
    {
        "bullet": "6",
        "requirement": "Traceability to source and transformations",
        "component": "frontend/components/ProvenancePanel.tsx",
        "fe_spec": "frontend/e2e/provenance.spec.ts",
        "be_spec": "backend/tests/test_cloudinary.py",
        "routes": "/v1/assets/{public_id}/provenance",
        "surface": "provenance-panel",
        "note": (
            "Full transformation chain, root hash, C2PA status, and a source badge "
            "on every panel. Fixture data is badged Fixture, never Live."
        ),
    },
]


def test_count(path: Path) -> int | None:
    if not path.exists():
        return None
    text = path.read_text()
    if path.suffix == ".ts":
        return len(re.findall(r"^\s*test\(", text, re.M))
    return len(re.findall(r"^\s*def test_", text, re.M))


def verify_references() -> list[str]:
    """Every path and test id must exist. A matrix pointing at nothing fails."""
    problems: list[str] = []
    for row in MATRIX:
        for key in ("component", "fe_spec", "be_spec"):
            p = REPO / row[key]
            if not p.exists():
                problems.append(f"bullet {row['bullet']}: missing {row[key]}")
        comp = REPO / row["component"]
        if comp.exists() and f'testId="{row["surface"]}"' not in comp.read_text():
            problems.append(
                f"bullet {row['bullet']}: {comp.name} has no "
                f'testId="{row["surface"]}"'
            )
    return problems


def main() -> int:
    problems = verify_references()
    if problems:
        for p in problems:
            print(f"FAIL: {p}", file=sys.stderr)
        return 1

    if not TIMELINE.exists():
        print(
            f"FAIL: {TIMELINE} missing. Run: (cd frontend && npx playwright test "
            "rubric-walkthrough)",
            file=sys.stderr,
        )
        return 1

    tl = json.loads(TIMELINE.read_text())
    offsets = {s["surface"]: s["offset_s"] for s in tl["surfaces"]}
    absent = [r["surface"] for r in MATRIX if r["surface"] not in offsets]
    if absent:
        print(f"FAIL: walkthrough did not record {absent}", file=sys.stderr)
        return 1

    total_walk = tl["walkthrough_seconds"]
    lines = [
        "# VERITAS dMRV — Rubric Traceability Matrix",
        "",
        f"**Generated:** {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')} "
        "· regenerate with `make rubric-matrix`",
        "",
        "Generated by `scripts/gen_rubric_matrix.py` from an actual run. The",
        "component paths, test ids and demo timestamps are verified against the",
        "tree before this file is written, so it cannot quietly drift out of date",
        "the way a hand-maintained matrix does.",
        "",
        "## What the timestamps are, precisely",
        "",
        f"Offsets into a **scripted walkthrough** at {tl['viewport']['width']}×"
        f"{tl['viewport']['height']}, {tl['configuration']}, measured on one",
        f"machine on {tl['generated_utc'][:10]}.",
        "",
        f"The full walkthrough takes **{total_walk} s**. That is time-to-reach, not",
        "time-to-present: it measures scrolling to a surface, not the speaking that",
        "happens once you are there. Treat it as a **floor**, and as the measured",
        "*order* of the demo — which is what `docs/14` §7.7 needs in order to re-cut",
        "the pitch to the real sequence.",
        "",
        "| Rubric | Requirement | Component | Demo offset | Tests |",
        "| :-- | :-- | :-- | --: | --: |",
    ]
    for row in MATRIX:
        fe = test_count(REPO / row["fe_spec"]) or 0
        be = test_count(REPO / row["be_spec"]) or 0
        lines.append(
            f"| **{row['bullet']}** | {row['requirement']} | "
            f"`{Path(row['component']).name}` | {offsets[row['surface']]:.2f} s | "
            f"{fe} e2e / {be} unit |"
        )

    lines += ["", "## Per-bullet detail", ""]
    for row in MATRIX:
        fe = test_count(REPO / row["fe_spec"]) or 0
        be = test_count(REPO / row["be_spec"]) or 0
        lines += [
            f"### Rubric {row['bullet']} — {row['requirement']}",
            "",
            f"- **Component:** `{row['component']}`",
            f"- **Backend route:** `{row['routes']}`",
            f"- **Frontend spec:** `{row['fe_spec']}` ({fe} tests)",
            f"- **Backend spec:** `{row['be_spec']}` ({be} tests)",
            f"- **Demo surface:** `{row['surface']}`, reached at "
            f"**{offsets[row['surface']]:.2f} s**",
            f"- **Note:** {row['note']}",
            "",
        ]

    lines += [
        "## Traceability to the demonstration script",
        "",
        "The walkthrough order above is the order `docs/14` §7.7 re-cuts the",
        "180-second pitch to follow. The pitch leads with rubric **3** and **5**",
        "rather than the carbon-market hook, because those are the two surfaces",
        "that show something working rather than something promised.",
        "",
        "## Known gaps in this matrix",
        "",
        "- **No human demo recording exists.** The offsets are scripted. A recorded",
        "  walkthrough would give real presentation timings; this gives a floor and",
        "  a verified order.",
        "- **`f_pdf` is unverified** — paid-plan only, free tier returns 401 — so",
        "  bullet 4's dossier is labelled plan-gated rather than demonstrated.",
        "- **The webhook signature scheme is unconfirmed** against a real",
        "  notification, so bullet 6's provenance chain is verified by unit test",
        "  and SDK replay rather than by an observed event.",
        "- **Registration cost is measured on synthetic scenes**, not photographic",
        "  imagery (see `docs/LOAD-TEST.md`).",
        "",
    ]
    OUT.write_text("\n".join(lines))
    print(f"wrote {OUT} ({len(MATRIX)} bullets, {total_walk}s walkthrough)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
