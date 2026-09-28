/**
 * Bundled search fixture.
 *
 * Reproduces the BACKEND's behaviour, including its limitation, rather than
 * pretending to be a neural index. A fixture that silently behaved better than
 * the real thing would make the demo look like a product it is not — and
 * `notes` is part of the contract precisely because the real backend is lexical.
 *
 * Scoring is corpus-rare-weighted term overlap, which is what tf-idf actually
 * does, so the relative ordering in fixture mode resembles live rather than
 * flattering.
 */

import { DEMO_ASSETS } from "./asset-fixture";
import type { SearchResponse, SearchResult } from "./search";

const STOPWORDS = new Set([
  "the", "a", "an", "of", "in", "on", "and", "or", "with", "for", "to", "at",
  "is", "are", "any", "some", "show", "find", "me", "all", "from",
]);

/**
 * A faithful port of `TfIdfSemanticBackend` in
 * `backend/services/semantic_service.py`.
 *
 * The first version of this fixture normalised by the sum of idf over all query
 * terms, which reported ~1.0 for everything — including a query where half the
 * terms matched NOTHING. The real backend returns 0.18 for that case, because
 * `_idf.get(t, 1.0)` gives an UNKNOWN term idf 1.0: it inflates the query
 * vector's norm and so shrinks the cosine. The fixture therefore made a
 * half-failed query look like a perfect match, which is precisely the
 * "behaves better than the real thing" failure it was written to avoid.
 *
 * So the formulas are ported rather than approximated:
 *   idf          log((1+n)/(1+df)) + 1        (scikit-learn smoothing)
 *   weight       (1 + log(tf)) * idf.get(t, 1.0)
 *   normalise    L2, on both document and query vectors
 *   score        sparse dot product, i.e. cosine over shared terms
 */
function tokenize(q: string): string[] {
  return q
    .toLowerCase()
    .split(/[^a-z0-9_-]+/)
    .filter((t) => t.length > 1 && !STOPWORDS.has(t));
}

type Vector = Record<string, number>;

function buildIndex(docs: string[][]): { idf: Record<string, number>; vectors: Vector[] } {
  const df: Record<string, number> = {};
  for (const tokens of docs) {
    for (const t of new Set(tokens)) df[t] = (df[t] ?? 0) + 1;
  }
  const n = docs.length;
  const idf: Record<string, number> = {};
  for (const [t, c] of Object.entries(df)) {
    idf[t] = Math.log((1 + n) / (1 + c)) + 1;
  }
  const vectors = docs.map((tokens) => {
    const tf: Record<string, number> = {};
    for (const t of tokens) tf[t] = (tf[t] ?? 0) + 1;
    return vectorize(tf, idf);
  });
  return { idf, vectors };
}

function vectorize(tf: Record<string, number>, idf: Record<string, number>): Vector {
  const vec: Vector = {};
  for (const [t, c] of Object.entries(tf)) {
    // The 1.0 default for an unseen term is load-bearing: see the note above.
    vec[t] = (1 + Math.log(c)) * (idf[t] ?? 1.0);
  }
  const norm = Math.sqrt(Object.values(vec).reduce((a, v) => a + v * v, 0));
  if (norm > 0) for (const t of Object.keys(vec)) vec[t] /= norm;
  return vec;
}

function cosine(qvec: Vector, dvec: Vector): number {
  let dot = 0;
  for (const [t, w] of Object.entries(qvec)) dot += w * (dvec[t] ?? 0);
  return dot;
}

export function searchFixture(q: string, k = 20): SearchResult {
  const terms = tokenize(q ?? "");

  const tokens = DEMO_ASSETS.map((a) => [
    ...a.tags.map((t) => t.toLowerCase()),
    a.esg_project_id.toLowerCase(),
    a.milestone_phase.toLowerCase(),
    a.sustainability_domain.toLowerCase(),
    a.public_id.toLowerCase(),
  ]);
  const { idf, vectors } = buildIndex(tokens);

  const qvec = terms.length ? vectorize(count(terms), idf) : {};
  const matchedInIndex = terms.filter((t) => t in idf);
  const unmatched = terms.filter((t) => !(t in idf)).sort();

  const scored = DEMO_ASSETS.map((a, i) => ({
    a,
    score: terms.length ? cosine(qvec, vectors[i]) : 0,
  }))
    .filter((s) => s.score > 0)
    .sort((x, y) => y.score - x.score);

  const haystack = (a: (typeof DEMO_ASSETS)[number]) =>
    `${a.tags.join(" ")} ${a.esg_project_id} ${a.milestone_phase} ${a.sustainability_domain} ${a.public_id}`.toLowerCase();

  const data: SearchResponse = {
    query: q ?? "",
    // Same name the backend uses, so the UI cannot accidentally imply otherwise.
    backend: "tfidf_lexical",
    total_indexed: DEMO_ASSETS.length,
    count: Math.min(k, scored.length),
    hits: scored.slice(0, k).map(({ a, score }) => ({
      asset_id: a.asset_id,
      score: Number(score.toFixed(4)),
      matched_terms: terms.filter((t) => haystack(a).includes(t)),
      tags: a.tags,
      excerpt: `${a.tags.join(" ")} · ${a.esg_project_id} · ${a.capture_timestamp} · canopy ${a.canopy_delta_pct ?? 0} percent`,
      jev_triage_decision: a.jev_triage_decision,
      c2pa_provenance: a.c2pa_provenance,
      capture_timestamp: a.capture_timestamp,
    })),
    unmatched_terms: unmatched,
    notes:
      "Bundled fixture, scored by a LEXICAL tf-idf vector space — the same " +
      "maths as the live backend (smoothed idf, sublinear term frequency, " +
      "L2-normalised sparse cosine), not a neural embedding model. It will " +
      "not match synonyms ('tree' will not find 'canopy').",
  };

  return {
    data,
    source: "fixture",
    reason: "Showing bundled fixture results — no search index was queried.",
  };
}

function count(items: string[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const t of items) out[t] = (out[t] ?? 0) + 1;
  return out;
}
