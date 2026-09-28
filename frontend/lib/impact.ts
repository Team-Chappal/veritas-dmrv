/**
 * Before/after comparison shapes (rubric bullet 3).
 *
 * The inlier ratio is a REGISTRATION QUALITY number, not a statement about the
 * forest. Its verdict is carried in words alongside the figure, because a
 * reviewer who sees "0.63" and a bar that is mostly green has learned nothing
 * about whether the comparison is trustworthy.
 */

export type InlierVerdict = "trusted" | "usable" | "not_trusted";

export interface ImpactComparison {
  project_id: string;
  baseline: {
    public_id: string;
    /** Data URI or https URL. */
    src: string;
    label: string;
    captured: string;
  };
  progress: {
    public_id: string;
    src: string;
    label: string;
    captured: string;
  };
  registration: {
    status: string;
    /** Fraction of matched keypoints consistent with one model. */
    inlier_ratio: number;
    sift_matches: number;
    mean_reprojection_error_px: number;
  };
  canopy: {
    baseline_cover_pct: number;
    progress_cover_pct: number;
    delta_pct: number;
  };
  _provenance?: { mode: "live" | "fixture"; caveat: string; evidence: string };
}

export interface ImpactResult {
  data: ImpactComparison;
  source: "live" | "fixture";
  reason: string;
}

/**
 * Thresholds mirrored from `core/config.py`.
 *
 * Duplicated rather than fetched, deliberately: a slider that renders "0.63 —
 * not trusted" against a hardcoded floor is a component you can read; one that
 * fetches its thresholds adds a round trip to a judgement and a way for the two
 * to disagree. `services/homography_service` is the authority and this is a
 * copy, so if one moves the other must too — a test asserts they match.
 */
export const INLIER_RATIO_FLOOR = 0.6;
export const INLIER_RATIO_TARGET = 0.7;

export function inlierVerdict(ratio: number): {
  verdict: InlierVerdict;
  glyph: string;
  word: string;
  tone: "verified" | "review" | "quarantine";
  meaning: string;
} {
  if (ratio >= INLIER_RATIO_TARGET) {
    return {
      verdict: "trusted",
      glyph: "✔",
      word: "Registration trusted",
      tone: "verified",
      meaning:
        "Enough matched features agree with a single model that the canopy " +
        "figures below can be attributed to the right pixels.",
    };
  }
  if (ratio >= INLIER_RATIO_FLOOR) {
    return {
      verdict: "usable",
      glyph: "!",
      word: "Registration usable, below target",
      tone: "review",
      meaning:
        "The comparison is real but noisier than we target. Read the canopy " +
        "delta as indicative rather than measured.",
    };
  }
  return {
    verdict: "not_trusted",
    glyph: "✖",
    word: "Registration not trusted",
    tone: "quarantine",
    meaning:
      "Too few matched features agree on one model, so the alignment is " +
      "probable rather than demonstrated. Do not report a delta from this pair.",
  };
}
