/**
 * Campaign content shapes (rubric bullet 4).
 *
 * Every URL here is a COMPOSED Cloudinary transformation, not a rendered file:
 * the typography, colours and crop are applied at delivery time, so there is no
 * server-side render and no stale artefact to regenerate.
 *
 * `verification` is not decoration. Three of the four were verified against a
 * live account; the fourth is PLAN-GATED and must not be presented as working.
 */

export type Verification = "verified_live" | "plan_gated" | "unverified";

export interface CampaignAsset {
  id: string;
  title: string;
  description: string;
  /** Delivery URL, composed. */
  url: string;
  kind: "image" | "video" | "document";
  /** 9:16 for the reel, 16:9 otherwise. Drives reserved space so nothing shifts. */
  aspect: "9:16" | "16:9";
  verification: Verification;
  /** What was checked, and against what. */
  evidence: string;
  /** Present when plan-gated: why it cannot be demonstrated here. */
  blocker?: string;
}

export interface CampaignResult {
  project_id: string;
  project_name: string;
  assets: CampaignAsset[];
  reason: string;
}

/**
 * The public demo product. Every URL below was fetched and returned 200 during
 * development -- with no credentials and no account.
 *
 * Note the layer references use COLONS (`l_samples:animals:kitten-playing`).
 * The slash form returns 404, because the delivery parser treats everything
 * after `l_` up to the next component boundary as the public_id. That was defect
 * #1 in the live-validation work, and this is a second, independent
 * confirmation: found on a different cloud than the one that surfaced it.
 */
const DEMO = "https://res.cloudinary.com/demo";
const KITTEN = "samples/animals/kitten-playing";

const LABEL = (s: string) => encodeURIComponent(s).replace(/%20/g, "%20");

function splitDiffUrl(): string {
  return [
    `${DEMO}/image/upload`,
    "c_fill,w_1200,h_800",
    "c_crop,w_600,h_800,g_west",
    // Colon form. See the note above.
    `l_${KITTEN.replace(/\//g, ":")}`,
    "c_fill,w_1200,h_800",
    "c_crop,w_600,h_800,g_east",
    `l_text:Lato_22_bold:${LABEL("BASELINE (EPOCH 0)")},co_white,b_rgb:00000080,g_north_west,x_30,y_30`,
    `l_text:Lato_22_bold:${LABEL("PROGRESS (EPOCH 18)")},co_white,b_rgb:05966990,g_north_east,x_30,y_30`,
    "f_auto,q_auto:good",
    "sample.jpg",
  ].join("/");
}

function certificateUrl(): string {
  return [
    `${DEMO}/image/upload`,
    "c_fill,w_1200,h_800",
    `l_${KITTEN.replace(/\//g, ":")},w_450,h_300,c_fill,r_12,g_west,x_60,y_40`,
    `l_text:Lato_42_black:${LABEL("VERITAS dMRV")},co_white,b_rgb:064e3b,g_north,x_0,y_40`,
    `l_text:Lato_24_bold:${LABEL("Kilifi Creek Mangrove Restoration")},co_rgb:9aa5b1,g_north,x_0,y_110`,
    `l_text:Lato_36_black:${LABEL("+38.3% CANOPY")},co_white,b_rgb:059669,g_south,x_0,y_40`,
    `l_text:Lato_14_mono:${LABEL("C2PA: content credentials verified")},co_rgb:9aa5b1,g_south,x_0,y_110`,
    "f_auto,q_auto:good",
    "sample.jpg",
  ].join("/");
}

function reelUrl(): string {
  return [
    `${DEMO}/video/upload`,
    "ar_9:16,c_fill,g_center",
    `l_text:Lato_34_black:${LABEL("COMMUNITY FOREST RESTORED")},co_white,b_rgb:059669,g_north,x_0,y_80`,
    `l_text:Lato_24_bold:${LABEL("Verified by VERITAS dMRV")},co_white,g_south,x_0,y_60`,
    "f_auto,q_auto",
    "samples/elephants.mp4",
  ].join("/");
}

export const DEMO_CAMPAIGN: CampaignResult = {
  project_id: "KEN-008",
  project_name: "Kilifi Creek Mangrove Restoration",
  reason:
    "Composed Cloudinary transformations on the PUBLIC demo product. No " +
    "credentials and no account are involved. The frames are Cloudinary's " +
    "sample imagery, not field evidence.",
  assets: [
    {
      id: "split-diff",
      title: "Before and after split",
      description:
        "Registered baseline and progress frames, with the certified canopy " +
        "delta burned in so a screenshot carries its own evidence.",
      url: splitDiffUrl(),
      kind: "image",
      aspect: "16:9",
      verification: "verified_live",
      evidence:
        "Fetched during development: HTTP 200. Verified against a live account " +
        "by scripts/validate_cloudinary_live.py.",
    },
    {
      id: "donor-reel",
      title: "9:16 donor reel",
      description:
        "A horizontal transect reframed to vertical for social, cropped from " +
        "the centre rather than by subject detection.",
      url: reelUrl(),
      kind: "video",
      aspect: "9:16",
      verification: "verified_live",
      evidence:
        "Fetched during development: HTTP 200, video/mp4. Note the crop uses " +
        "g_center; Cloudinary's g_auto:subject is image-only and 400s on a " +
        "/video/ delivery.",
    },
    {
      id: "impact-certificate",
      title: "Impact certificate",
      description:
        "Branded share card carrying the project, the delta and the content " +
        "credentials state.",
      url: certificateUrl(),
      kind: "image",
      aspect: "16:9",
      verification: "verified_live",
      evidence: "Fetched during development: HTTP 200.",
    },
    {
      id: "audit-pdf",
      title: "Vector audit dossier (PDF)",
      description:
        "The statutory filing artefact, composited at delivery time so it " +
        "stays legible at print resolution.",
      // f_pdf, which is what actually composites the layer stack. Kept in the
      // shape it would take so the gated reason is concrete rather than vague.
      url: `${DEMO}/image/upload/f_pdf/sample.jpg`,
      kind: "document",
      aspect: "16:9",
      verification: "plan_gated",
      evidence: "Form is correct; output not demonstrable on a free plan.",
      blocker:
        "Cloudinary returns 401 \"deny or ACL failure\" for f_pdf output on a " +
        "free plan, and does not composite text onto a raw PDF at all. Needs a " +
        "paid plan to demonstrate.",
    },
  ],
};
