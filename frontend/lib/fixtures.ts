/**
 * Bundled provenance fixtures.
 *
 * S6 exit criterion 5 is that the demo works with the backend entirely absent,
 * and a stage demo on conference wifi is the normal case, not the exception. So
 * the provenance panel needs data when there is no API — but it must never let a
 * reader mistake it for the real thing.
 *
 * The hashes below are the SHA-256 of the empty string and of "veritas", which
 * are the well-known published values, NOT measurements of any real asset. A
 * plausible-looking random digest would be indistinguishable from a measured one
 * in a screenshot, and that is precisely the failure being guarded against.
 */

import type { ProvenanceRecord } from "./provenance";

export const DEMO_ASSET_ID = "impact_evidence/KEN-042/raw_capture_month18";

/** SHA-256 of the empty string. Published constant, not a measurement. */
const DEMO_ROOT_HASH =
  "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";

export const DEMO_PROVENANCE: ProvenanceRecord = {
  public_id: DEMO_ASSET_ID,
  master: {
    public_id: DEMO_ASSET_ID,
    folder: "impact_evidence/KEN-042",
    asset_type: "image",
  },
  content_hash: {
    algorithm: "SHA-256",
    root_hash: DEMO_ROOT_HASH,
  },
  c2pa_provenance: "C2PA_VERIFIED",
  transformations: [
    {
      transformation: "c_fill,w_1200,h_800",
      width: 1200,
      height: 800,
      format: "png",
      bytes: 1_486_592,
    },
    {
      transformation: "c_fill,w_1200,h_800/c_crop,w_600,h_800,g_west",
      width: 1200,
      height: 800,
      format: "png",
      bytes: 1_204_880,
    },
    {
      transformation:
        "c_fill,w_1200,h_800/c_crop,w_600,h_800,g_west/l_text:Lato_22_bold:BASELINE,g_north_west,x_30,y_30",
      width: 1200,
      height: 800,
      format: "jpg",
      bytes: 318_402,
    },
  ],
  transformation_log_live: false,
  note:
    "Bundled fixture. No Cloudinary call was made. Run " +
    "scripts/validate_cloudinary_live.py to exercise the live path.",
};

export const DEMO_REASON =
  "No backend reachable. Showing bundled fixture data — no Cloudinary call was made.";
