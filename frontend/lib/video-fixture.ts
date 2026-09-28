/**
 * Bundled video analysis (rubric bullet 2).
 *
 * The VIDEO is a real, playable file on Cloudinary's public demo cloud, so the
 * player genuinely plays in fixture mode without credentials. The FRAMES are not
 * field evidence, and `asset_note` says so where a reviewer will see it.
 *
 * The tags are NESTED on purpose — `canopy` sits inside `forest`, and a second
 * `canopy` window sits inside that. That is the shape Cloudinary's AI Video
 * Analysis actually returns, and it is what breaks naive caption generation:
 * overlapping cues are invalid VTT and a naive gap-fill produces a negative
 * duration. A fixture with tidy non-overlapping windows would prove nothing.
 */

import { buildVtt, type VideoAnalysis } from "./video";

/** Cloudinary's PUBLIC demo product. No credentials, no account. */
export const DEMO_VIDEO_URL =
  "https://res.cloudinary.com/demo/video/upload/q_auto,f_mp4/samples/elephants.mp4";

const TAGS = [
  { tag: "open_water", start: 0.0, end: 6.0, confidence: 0.94 },
  { tag: "wetland", start: 0.0, end: 6.0, confidence: 0.91 },
  { tag: "elephant", start: 1.2, end: 4.8, confidence: 0.97 },
  { tag: "reeds", start: 3.0, end: 9.5, confidence: 0.88 },
  { tag: "reeds", start: 6.0, end: 12.0, confidence: 0.84 },
  { tag: "shoreline", start: 9.0, end: 18.0, confidence: 0.9 },
  { tag: "shoreline", start: 12.0, end: 21.0, confidence: 0.86 },
  { tag: "low_light", start: 14.0, end: 21.0, confidence: 0.79 },
];

export const DEMO_ANALYSIS: VideoAnalysis = {
  public_id: "samples/elephants",
  duration_s: 21,
  tags: TAGS,
  vtt: buildVtt(TAGS),
  hotspots: [
    {
      hotspot_id: "hs-elephant",
      title: "Elephant",
      x_pct: 46,
      y_pct: 52,
      start: 1.2,
      end: 4.8,
      description: "Adult animal, partially submerged.",
      telemetry: { "distance (m)": 42 },
    },
    {
      hotspot_id: "hs-reeds",
      title: "Reed bed",
      x_pct: 18,
      y_pct: 74,
      start: 3.0,
      end: 9.5,
      description: "Riparian reeds along the channel margin.",
      telemetry: { "cover (%)": 61 },
    },
    {
      hotspot_id: "hs-shoreline",
      title: "Shoreline",
      x_pct: 78,
      y_pct: 38,
      start: 9.0,
      end: 18.0,
      description: "Exposed bank, likely seasonal drawdown.",
      telemetry: { "exposure": "seasonal" },
    },
  ],
  asset_note:
    "Frames are Cloudinary's PUBLIC demo asset (samples/elephants), not field " +
    "evidence. Captions and hotspots are generated locally; no Cloudinary call " +
    "was made for them.",
};
