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

function apiBase(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

/** Classify a response that arrived. Status 200 is not sufficient. */
function classify(record: ProvenanceRecord): ProvenanceResult {
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
