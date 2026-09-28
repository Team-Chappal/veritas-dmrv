/**
 * Bundled before/after fixture for the impact studio.
 *
 * The two "photos" are generated SVG scenes rather than shipped bitmaps: they
 * must differ visibly at the slider (more canopy green in the progress frame) or
 * the component demonstrates nothing, and they must be obviously synthetic so a
 * screenshot cannot be mistaken for field evidence.
 *
 * The inlier ratio is set just below target on purpose. A fixture parked at 0.95
 * would only ever exercise the "trusted" branch, and the branch that matters most
 * — "usable, read the delta as indicative" — would ship untested.
 */

import type { ImpactResult } from "./impact";

/** Deterministic canopy blobs, so the two frames differ in a controlled way. */
function scene(
  seed: number,
  canopyPct: number,
  label: string,
  tint: string
): string {
  let s = seed >>> 0;
  const rand = () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0x100000000;
  };

  const blobs: string[] = [];
  const wanted = Math.round(canopyPct * 1.6);
  for (let i = 0; i < wanted; i++) {
    const cx = 30 + rand() * 740;
    const cy = 40 + rand() * 300;
    const r = 18 + rand() * 46;
    // A trunk under each blob, so it reads as canopy rather than noise.
    const trunkX = cx - 3;
    blobs.push(
      `<line x1="${trunkX.toFixed(1)}" y1="${(cy + r).toFixed(1)}" x2="${trunkX.toFixed(1)}" y2="400" stroke="#5b4632" stroke-width="4"/>`,
      `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${r.toFixed(1)}" fill="${tint}" opacity="0.9"/>`
    );
  }

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 420" width="800" height="420" role="img">
  <rect width="800" height="420" fill="#1a2a1f"/>
  <rect y="360" width="800" height="60" fill="#3a2f22"/>
  ${blobs.join("\n  ")}
  <text x="16" y="30" font-family="monospace" font-size="16" fill="#e2e8f0">${label}</text>
  <text x="16" y="404" font-family="monospace" font-size="13" fill="#94a3b8">SYNTHETIC SCENE — not field evidence</text>
</svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

const BASELINE_COVER = 12.4;
const PROGRESS_COVER = 44.1;

export const DEMO_COMPARISON: ImpactResult = {
  source: "fixture",
  reason:
    "Showing a synthetic before/after pair. No SIFT registration was run and " +
    "no Cloudinary call was made.",
  data: {
    project_id: "KEN-008",
    baseline: {
      public_id: "impact_evidence/KEN-008/baseline_month_0/plate_01",
      src: scene(7, BASELINE_COVER, "BASELINE (month 0)", "#2f7d4f"),
      label: "Baseline",
      captured: "2025-03-15",
    },
    progress: {
      public_id: "impact_evidence/KEN-008/progress_month_18/plate_01",
      src: scene(19, PROGRESS_COVER, "PROGRESS (month 18)", "#3fa35f"),
      label: "Progress",
      captured: "2026-09-20",
    },
    registration: {
      // Below the 0.70 target, above the 0.60 floor: the branch that says
      // "usable, read the delta as indicative" is the one worth demonstrating.
      status: "ALIGNED_HOMOGRAPHY",
      inlier_ratio: 0.66,
      sift_matches: 1843,
      mean_reprojection_error_px: 2.4,
    },
    canopy: {
      baseline_cover_pct: BASELINE_COVER,
      progress_cover_pct: PROGRESS_COVER,
      delta_pct: PROGRESS_COVER - BASELINE_COVER,
    },
  },
};
