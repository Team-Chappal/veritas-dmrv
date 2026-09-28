/**
 * Typed shapes for the provenance surface (rubric bullet 6).
 *
 * Kept separate from the fetch layer so a component never has to know where its
 * data came from, and so the fixture and the live response are checked against
 * the SAME type. A fixture that drifts from the API is a fixture that lies, and
 * a lying fixture in a verification product is worse than no fixture.
 */

/** What the backend's provenance middleware stamps on every JSON response. */
export interface ProvenanceBlock {
  request_id: string;
  generated_at: string;
  mode: "live" | "fixture";
  evidence: string;
  app_env: string;
  elapsed_ms: number;
  path: string;
  method: string;
  provenance_endpoint: string;
  caveat: string;
}

export interface MasterAsset {
  public_id: string;
  folder: string;
  asset_type: string;
}

export interface ContentHash {
  algorithm: string;
  root_hash: string;
}

export interface TransformationStep {
  /** Cloudinary's transformation string, e.g. `c_fill,w_1200,h_800`. */
  transformation?: string;
  width?: number;
  height?: number;
  bytes?: number;
  format?: string;
  url?: string;
  secure_url?: string;
}

export type C2PAStatus =
  | "C2PA_VERIFIED"
  | "C2PA_MISSING"
  | "C2PA_MUTATED"
  | (string & {});

export interface ProvenanceRecord {
  public_id: string;
  master: MasterAsset;
  content_hash: ContentHash;
  c2pa_provenance: C2PAStatus;
  transformations: TransformationStep[];
  transformation_log_live: boolean;
  note: string;
  /** Present on live responses only. */
  _provenance?: ProvenanceBlock;
}

/**
 * Where a record came from, and if not live, WHY.
 *
 * `reason` is not decoration. A panel that silently shows fixture data as if it
 * were live is the exact failure this project exists to prevent, so the
 * degradation travels with the data and the UI is required to render it.
 */
export interface ProvenanceResult {
  record: ProvenanceRecord;
  source: "live" | "fixture";
  reason: string;
}
