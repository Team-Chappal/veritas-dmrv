/**
 * Asset-collection shapes (rubric bullet 1).
 *
 * Kept separate from the fetch layer so the fixture and the live response are
 * checked against the SAME type, as with the provenance surface.
 */

export type TriageDecision =
  | "VERIFIED_PASS"
  | "REVIEW_AMBIGUOUS"
  | "QUARANTINE_FRAUD"
  | (string & {});

export type C2PAStatus = "C2PA_VERIFIED" | "C2PA_MISSING" | "C2PA_MUTATED" | (string & {});

export interface AssetSummary {
  asset_id: string;
  public_id: string;
  esg_project_id: string;
  milestone_phase: string;
  sustainability_domain: string;
  capture_timestamp: string;
  media_type: string;
  jev_triage_decision: TriageDecision;
  jev_confidence_score: number;
  c2pa_provenance: C2PAStatus;
  canopy_delta_pct: number | null;
  tags: string[];
}

export interface FacetCounts {
  decision: Record<string, number>;
  phase: Record<string, number>;
  c2pa: Record<string, number>;
  domain: Record<string, number>;
}

export interface AssetListResponse {
  total_matched: number;
  returned: number;
  offset: number;
  limit: number;
  has_more: boolean;
  facets: FacetCounts;
  assets: AssetSummary[];
  _provenance?: { mode: "live" | "fixture"; caveat: string; evidence: string };
}

export interface AssetFilters {
  project_id?: string;
  phase?: string;
  decision?: string;
  domain?: string;
  tag?: string;
  c2pa?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

export interface AssetListResult {
  data: AssetListResponse;
  source: "live" | "fixture";
  reason: string;
}
