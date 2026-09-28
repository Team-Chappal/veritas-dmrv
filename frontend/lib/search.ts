/**
 * Search shapes (rubric bullet 5).
 *
 * The important fields are the ones about what the search DID NOT do:
 * `backend`, `unmatched_terms` and `notes`. A semantic search that silently
 * behaves lexically is worse than one that admits it, and `notes` is the
 * backend telling us so in as many words.
 */

export type SearchBackend = string;

export interface SearchHit {
  asset_id: string;
  score: number;
  matched_terms: string[];
  tags: string[];
  excerpt: string;
  /** Present on live responses; the collection endpoint's asset shape. */
  jev_triage_decision?: string;
  c2pa_provenance?: string;
  capture_timestamp?: string;
}

export interface SearchResponse {
  query: string;
  backend: SearchBackend;
  total_indexed: number;
  count: number;
  hits: SearchHit[];
  unmatched_terms: string[];
  notes: string;
  _provenance?: { mode: "live" | "fixture"; caveat: string; evidence: string };
}

export interface SearchResult {
  data: SearchResponse;
  source: "live" | "fixture";
  reason: string;
}
