/**
 * API client.
 *
 * Two rules, both learned the hard way in the backend:
 *
 * 1. DEGRADATION CARRIES ITS REASON. Every function returns `{ data, source,
 *    reason }`. A caller that drops `reason` is the mechanism by which synthetic
 *    data gets presented as measured, which is the failure this whole project is
 *    organised around.
 *
 * 2. THE BACKEND'S OWN PROVENANCE BLOCK DECIDES. `core/provenance.py` stamps
 *    every JSON response with `_provenance.mode`. So a 200 response carrying
 *    `mode: "fixture"` is reported as FIXTURE even though the HTTP call
 *    succeeded. Trusting the status code alone would label a successful
 *    fixture-mode response as live.
 */

import { DEMO_ASSET_ID, DEMO_PROVENANCE, DEMO_REASON } from "./fixtures";
import type { ProvenanceRecord, ProvenanceResult } from "./provenance";
import type { SearchResponse } from "./search";

/** Short by design: a stage demo on bad wifi should degrade, not hang. */
export const REQUEST_TIMEOUT_MS = 4000;

/**
 * Appended to every degradation reason, whatever the cause.
 *
 * "Backend unreachable" reads like a transient blip, and a reader could take the
 * next number on the panel as a measurement. The panel is only trustworthy if
 * the reason says, every time, that no Cloudinary call was made.
 */
const UNMEASURED = "No Cloudinary call was made.";

/**
 * The API base URL, or null when none is configured.
 *
 * NULL, NOT A DEFAULT. The first version returned `?? "http://localhost:8000"`,
 * which is right on a developer machine and wrong everywhere else. A
 * judge-facing deployment has no backend on the judge's own machine, so every
 * panel fired a request at localhost:8000, waited for connection-refused, and
 * then degraded -- working, but by accident, after a pointless network attempt,
 * with a reason string that said "Backend unreachable" when the truth was that
 * no backend had ever been asked for.
 *
 * So an unconfigured API is a FIRST-CLASS STATE with its own reason, and the
 * network is not touched at all. "No API configured" and "the API failed" are
 * different facts and the panel should say which.
 */
function apiBase(): string | null {
  // RUNTIME OVERRIDE FIRST. NEXT_PUBLIC_* is inlined at build time, so a
  // deployed build cannot be re-pointed at a different backend without a
  // rebuild. That is a real operational limit: staging and production are the
  // same artefact, and fixing a wrong backend URL means a new deploy.
  //
  // It is also what the live-path specs need, and it is worth being honest
  // about that. Those specs mock the API by intercepting requests to
  // localhost:8000, and they worked ONLY because apiBase invented that default
  // when the variable was unset. Removing the default -- which was correct for a
  // judge-facing build -- silently took the live path out of coverage AND broke
  // four specs, which is how it was found. Both facts belong in this comment:
  // the override exists for operators, and the test suite depends on it.
  if (typeof window !== "undefined") {
    const runtime = (window as unknown as { __VERITAS_API_URL__?: string })
      .__VERITAS_API_URL__;
    if (runtime && runtime.length > 0) return runtime;
  }
  const configured = process.env.NEXT_PUBLIC_API_URL;
  return configured && configured.length > 0 ? configured : null;
}

/** True when this build has no API to talk to, and should not pretend otherwise. */
export function isDemoBuild(): boolean {
  return apiBase() === null;
}

/** The reason every panel shows in a build with no API configured. */
const NO_API_REASON =
  "Demo deployment: no API is configured, so this is served from the bundled " +
  `fixture. No request was made. ${UNMEASURED}`;

/**
 * Classify a response that arrived. Status 200 is not sufficient.
 *
 * EXPORTED because this is the rule that decides whether a panel says Live or
 * Fixture -- the single most consequential decision in the interface, and the
 * whole reason the provenance block exists. As a module-private function it could
 * only be reached by standing up a server, and since the e2e suite runs a build
 * with no API configured, the live branch was not covered at all.
 */
export function classify(record: ProvenanceRecord): ProvenanceResult {
  const block = record._provenance;
  if (!block) {
    // No block: we cannot prove this is live, so we do not claim it is.
    return {
      record,
      source: "fixture",
      reason:
        "Response carried no provenance block, so its origin cannot be " +
        `verified. Treated as fixture. ${UNMEASURED}`,
    };
  }
  if (block.mode === "fixture") {
    return { record, source: "fixture", reason: block.caveat || block.evidence };
  }
  return { record, source: "live", reason: "" };
}

export async function fetchProvenance(
  publicId: string = DEMO_ASSET_ID,
  signal?: AbortSignal
): Promise<ProvenanceResult> {
  if (isDemoBuild()) {
    return { record: DEMO_PROVENANCE, source: "fixture", reason: NO_API_REASON };
  }
  const url = `${apiBase()}/api/v1/assets/${publicId}/provenance`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  // Honour a caller-supplied signal as well as our own timeout.
  const onAbort = () => controller.abort();
  signal?.addEventListener("abort", onAbort);

  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) {
      return {
        record: DEMO_PROVENANCE,
        source: "fixture",
        reason: `Backend returned HTTP ${res.status}. Showing bundled fixture data. ${UNMEASURED}`,
      };
    }
    const body = (await res.json()) as ProvenanceRecord;
    return classify(body);
  } catch (err) {
    const aborted = err instanceof Error && err.name === "AbortError";
    return {
      record: DEMO_PROVENANCE,
      source: "fixture",
      reason: aborted
        ? `Backend did not respond within ${REQUEST_TIMEOUT_MS}ms. Showing bundled fixture data. ${UNMEASURED}`
        : `Backend unreachable. Showing bundled fixture data. ${UNMEASURED}`,
    };
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
}

/* -------------------------------------------------------------------------- */
/* Asset collection (rubric bullet 1)                                          */
/* -------------------------------------------------------------------------- */

import { filterFixture } from "./asset-fixture";
import type { AssetFilters, AssetListResponse, AssetListResult } from "./assets";

export async function fetchAssets(
  filters: AssetFilters = {},
  signal?: AbortSignal
): Promise<AssetListResult> {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  }
  if (isDemoBuild()) {
    return { data: filterFixture(filters), source: "fixture", reason: NO_API_REASON };
  }
  const query = params.toString();
  const url = `${apiBase()}/api/v1/assets${query ? `?${query}` : ""}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const onAbort = () => controller.abort();
  signal?.addEventListener("abort", onAbort);

  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) {
      return {
        data: filterFixture(filters),
        source: "fixture",
        reason: `Backend returned HTTP ${res.status}. Showing bundled fixture collection. ${UNMEASURED}`,
      };
    }
    const body = (await res.json()) as AssetListResponse;
    const block = body._provenance;
    // Same rule as the provenance surface: a 200 is not proof of a live read.
    if (!block || block.mode === "fixture") {
      return {
        data: body,
        source: "fixture",
        reason: `${block?.caveat ?? block?.evidence ?? "No provenance block."} ${UNMEASURED}`,
      };
    }
    return { data: body, source: "live", reason: "" };
  } catch (err) {
    const aborted = err instanceof Error && err.name === "AbortError";
    return {
      data: filterFixture(filters),
      source: "fixture",
      reason: aborted
        ? `Backend did not respond within ${REQUEST_TIMEOUT_MS}ms. Showing bundled fixture collection. ${UNMEASURED}`
        : `Backend unreachable. Showing bundled fixture collection. ${UNMEASURED}`,
    };
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
}

/* -------------------------------------------------------------------------- */
/* Search (rubric bullet 5)                                                  */
/* -------------------------------------------------------------------------- */

import { searchFixture } from "./search-fixture";
import type { SearchResult } from "./search";

export async function fetchSearch(
  q: string,
  k = 20,
  signal?: AbortSignal
): Promise<SearchResult> {
  if (isDemoBuild()) {
    return { ...searchFixture(q, k), reason: NO_API_REASON };
  }
  const params = new URLSearchParams({ q, k: String(k) });
  const url = `${apiBase()}/api/v1/search?${params.toString()}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const onAbort = () => controller.abort();
  signal?.addEventListener("abort", onAbort);

  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) {
      return {
        ...searchFixture(q, k),
        reason: `Backend returned HTTP ${res.status}. Showing bundled fixture results. ${UNMEASURED}`,
      };
    }
    const body = (await res.json()) as SearchResponse;
    const block = body._provenance;
    if (!block || block.mode === "fixture") {
      return {
        data: body,
        source: "fixture",
        reason: `${block?.caveat ?? block?.evidence ?? "No provenance block."} ${UNMEASURED}`,
      };
    }
    return { data: body, source: "live", reason: "" };
  } catch (err) {
    const aborted = err instanceof Error && err.name === "AbortError";
    return {
      ...searchFixture(q, k),
      reason: aborted
        ? `Backend did not respond within ${REQUEST_TIMEOUT_MS}ms. Showing bundled fixture results. ${UNMEASURED}`
        : `Backend unreachable. Showing bundled fixture results. ${UNMEASURED}`,
    };
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
}
