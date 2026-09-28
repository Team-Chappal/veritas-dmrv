/**
 * Bundled asset-collection fixture.
 *
 * The live corpus is 520 assets. Shipping 520 rows of fixture would bloat the
 * bundle for a page that only ever displays a page of results, so this
 * generates a smaller but STRUCTURALLY COMPLETE collection: every decision, C2PA
 * state, phase and domain appears with realistic counts, so the filter chips and
 * the "N of M" summary behave the way they do live.
 *
 * Generated deterministically from a fixed seed — the same asset appears on
 * every reload, so a screenshot taken today matches one taken tomorrow.
 */

import type {
  AssetListResponse,
  AssetSummary,
  FacetCounts,
} from "./assets";

/** Small deterministic PRNG. Not security-relevant; it only has to be stable. */
function rng(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0x100000000;
  };
}

const PROJECTS = ["KEN-008", "BRA-314", "ESP-200", "TUR-101"];
const PHASES = [
  "baseline_month_0",
  "progress_month_6",
  "progress_month_18",
  "certified_year_3",
];
const DOMAINS = [
  "mangrove_restoration",
  "reforestation",
  "clean_water",
  "solar_microgrid",
];
const TAG_POOL = [
  "canopy",
  "mangrove",
  "water",
  "wetland",
  "bare_soil",
  "ground_level",
  "aerial",
  "overcast",
  "harsh_sun",
];
const DECISIONS: Array<[string, number]> = [
  ["VERIFIED_PASS", 0.7],
  ["REVIEW_AMBIGUOUS", 0.21],
  ["QUARANTINE_FRAUD", 0.09],
];
const C2PA_STATES: Array<[string, number]> = [
  ["C2PA_VERIFIED", 0.78],
  ["C2PA_MISSING", 0.13],
  ["C2PA_MUTATED", 0.09],
];

function pick<T>(r: () => number, pairs: Array<[T, number]>): T {
  const roll = r();
  let acc = 0;
  for (const [value, weight] of pairs) {
    acc += weight;
    if (roll <= acc) return value;
  }
  return pairs[pairs.length - 1][0];
}

const SAMPLE_SIZE = 64;

function buildAssets(): AssetSummary[] {
  const r = rng(20260928);
  const out: AssetSummary[] = [];
  for (let i = 0; i < SAMPLE_SIZE; i++) {
    const project = PROJECTS[Math.floor(r() * PROJECTS.length)];
    const phase = PHASES[Math.floor(r() * PHASES.length)];
    const tagCount = 2 + Math.floor(r() * 3);
    const tags: string[] = [];
    for (let t = 0; t < tagCount; t++) {
      const tag = TAG_POOL[Math.floor(r() * TAG_POOL.length)];
      if (!tags.includes(tag)) tags.push(tag);
    }
    const month = 1 + Math.floor(r() * 12);
    const day = 1 + Math.floor(r() * 28);
    out.push({
      asset_id: `${project.toLowerCase()}/${phase}/a${String(i).padStart(4, "0")}`,
      public_id: `impact_evidence/${project}/${phase}/a${String(i).padStart(4, "0")}`,
      esg_project_id: project,
      milestone_phase: phase,
      sustainability_domain: DOMAINS[Math.floor(r() * DOMAINS.length)],
      capture_timestamp: `202${5 + Math.floor(r() * 2)}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
      media_type: r() > 0.85 ? "video" : "image",
      jev_triage_decision: pick(r, DECISIONS),
      jev_confidence_score: 40 + Math.floor(r() * 60),
      c2pa_provenance: pick(r, C2PA_STATES),
      canopy_delta_pct: r() > 0.3 ? Number((r() * 60).toFixed(2)) : null,
      tags,
    });
  }
  return out.sort((a, b) => b.capture_timestamp.localeCompare(a.capture_timestamp));
}

export const DEMO_ASSETS: AssetSummary[] = buildAssets();

function facet(assets: AssetSummary[], key: keyof AssetSummary): Record<string, number> {
  const out: Record<string, number> = {};
  for (const a of assets) {
    const v = a[key];
    if (typeof v === "string") out[v] = (out[v] ?? 0) + 1;
  }
  return Object.fromEntries(Object.entries(out).sort((x, y) => y[1] - x[1]));
}

/**
 * Mirrors the backend's filter AND facet semantics, so fixture mode behaves
 * identically. The facet lift matters: counting an axis with its own filter
 * applied collapses it to the single selected value, the other chips vanish, and
 * the reviewer is trapped in the filter they just applied.
 */
function applyFilters(
  rows: AssetSummary[],
  f: { [k: string]: string | number | undefined },
  skip?: string
): AssetSummary[] {
  let out = rows;
  if (f.project_id && skip !== "project_id")
    out = out.filter((a) => a.esg_project_id === f.project_id);
  if (f.phase && skip !== "phase") out = out.filter((a) => a.milestone_phase === f.phase);
  if (f.decision && skip !== "decision")
    out = out.filter((a) => a.jev_triage_decision === f.decision);
  if (f.domain && skip !== "domain")
    out = out.filter((a) => a.sustainability_domain === f.domain);
  if (f.tag) out = out.filter((a) => a.tags.includes(String(f.tag)));
  if (f.c2pa && skip !== "c2pa") out = out.filter((a) => a.c2pa_provenance === f.c2pa);
  if (f.q) {
    const n = String(f.q).toLowerCase();
    out = out.filter(
      (a) => a.public_id.toLowerCase().includes(n) || a.tags.some((t) => t.toLowerCase().includes(n))
    );
  }
  return out;
}

const FACET_AXES: Array<[keyof FacetCounts, keyof AssetSummary]> = [
  ["decision", "jev_triage_decision"],
  ["phase", "milestone_phase"],
  ["c2pa", "c2pa_provenance"],
  ["domain", "sustainability_domain"],
];

export function filterFixture(f: {
  project_id?: string;
  phase?: string;
  decision?: string;
  domain?: string;
  tag?: string;
  c2pa?: string;
  q?: string;
  limit?: number;
  offset?: number;
}): AssetListResponse {
  const rows = applyFilters(DEMO_ASSETS, f);

  const limit = f.limit ?? 24;
  const offset = f.offset ?? 0;
  // Each axis counted with its OWN filter lifted, matching the backend.
  const facets = {} as FacetCounts;
  for (const [axis, field] of FACET_AXES) {
    facets[axis] = facet(applyFilters(DEMO_ASSETS, f, axis), field);
  }

  return {
    total_matched: rows.length,
    returned: Math.max(0, Math.min(limit, rows.length - offset)),
    offset,
    limit,
    has_more: offset + limit < rows.length,
    facets,
    assets: rows.slice(offset, offset + limit),
  };
}
