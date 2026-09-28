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

/** Rarity across the corpus, so a rare term outweighs a common one. */
function idf(term: string, docs: string[][]): number {
  const withTerm = docs.filter((d) => d.includes(term)).length;
  if (withTerm === 0) return 0;
  return Math.log(docs.length / withTerm) + 1;
}

export function searchFixture(q: string, k = 20): SearchResult {
  const query = (q ?? "").trim().toLowerCase();
  const docs = DEMO_ASSETS.map((a) => [
    ...a.tags.map((t) => t.toLowerCase()),
    a.esg_project_id.toLowerCase(),
    a.milestone_phase.toLowerCase(),
    a.sustainability_domain.toLowerCase(),
    a.public_id.toLowerCase(),
  ]);

  const terms = query
    .split(/[^a-z0-9_-]+/)
    .filter((t) => t.length > 1 && !STOPWORDS.has(t));

  const unmatched: string[] = [];
  const hits = [];

  if (terms.length) {
    for (const term of terms) if (idf(term, docs) === 0) unmatched.push(term);

    for (const a of DEMO_ASSETS) {
      const haystack = `${a.tags.join(" ")} ${a.esg_project_id} ${a.milestone_phase} ${a.sustainability_domain} ${a.public_id}`.toLowerCase();
      const matched = terms.filter((t) => haystack.includes(t));
      if (!matched.length) continue;
      // Same shape as the real scorer: matched-term idf, normalised.
      const raw = matched.reduce((acc, t) => acc + idf(t, docs), 0);
      const max = terms.reduce((acc, t) => acc + Math.max(idf(t, docs), 0.0001), 0);
      hits.push({
        asset_id: a.asset_id,
        score: Number((raw / (max || 1)).toFixed(4)),
        matched_terms: matched,
        tags: a.tags,
        excerpt: `${a.tags.join(" ")} · ${a.esg_project_id} · ${a.capture_timestamp} · canopy ${a.canopy_delta_pct ?? 0} percent`,
        jev_triage_decision: a.jev_triage_decision,
        c2pa_provenance: a.c2pa_provenance,
        capture_timestamp: a.capture_timestamp,
      });
    }
  }

  hits.sort((x, y) => y.score - x.score);

  const data: SearchResponse = {
    query: q ?? "",
    // Same name the backend uses, so the UI cannot accidentally imply otherwise.
    backend: "tfidf_lexical",
    total_indexed: DEMO_ASSETS.length,
    count: Math.min(k, hits.length),
    hits: hits.slice(0, k),
    unmatched_terms: unmatched,
    notes:
      "Bundled fixture scored the same way the live backend scores: lexical " +
      "tf-idf term overlap weighted by corpus rarity. It will not match " +
      "synonyms ('tree' will not find 'canopy').",
  };

  return {
    data,
    source: "fixture",
    reason: "Showing bundled fixture results — no search index was queried.",
  };
}
