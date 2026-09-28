/**
 * Video player shapes (rubric bullet 2).
 *
 * The caption track is a real media file with a strict grammar, and the two ways
 * it fails are silent. `buildVtt` here mirrors the backend's
 * `services/video_service.py`: Cloudinary's tagging returns NESTED windows (a
 * `canopy` segment inside a `forest` segment), overlapping cues are invalid
 * VTT, and the original backend gap logic produced a NEGATIVE duration. The
 * timeline is therefore swept into atomic intervals and nested tags share a cue
 * as separate lines.
 */

export interface VideoTag {
  tag: string;
  start: number;
  end: number;
  confidence: number;
}

export interface VideoHotspot {
  hotspot_id: string;
  title: string;
  /** Percentage of frame width, so it survives a responsive player. */
  x_pct: number;
  y_pct: number;
  start: number;
  end: number;
  description?: string;
  telemetry?: Record<string, string | number>;
}

export interface VideoAnalysis {
  public_id: string;
  duration_s: number;
  tags: VideoTag[];
  vtt: string;
  hotspots: VideoHotspot[];
  /** Honest about what the frames are. */
  asset_note: string;
}

const DEFAULT_MIN_CUE_S = 0.8;
const GAP_S = 0.1;

/** Seconds to `HH:MM:SS.mmm`. */
export function formatTimestamp(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "00:00:00.000";
  const ms = Math.round(seconds * 1000);
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  const rem = ms % 1000;
  const p = (n: number, w = 2) => String(n).padStart(w, "0");
  return `${p(h)}:${p(m)}:${p(s)}.${p(rem, 3)}`;
}

function encodeCueText(text: string): string {
  return text.replace(/\n/g, " ").replace(/-->/g, "->").trim();
}

/**
 * Sweep the tag windows into non-overlapping cues.
 *
 * Boundaries come from every window edge, so an interval is emitted only when no
 * tag starts or stops inside it — which is what makes the cues valid. Any tag
 * active during an interval becomes a line in that cue, so nesting is preserved
 * as multiple lines rather than dropped or overlapped.
 */
export function buildVtt(
  tags: VideoTag[],
  opts: { minCueSeconds?: number; maxLines?: number } = {}
): string {
  const minCue = opts.minCueSeconds ?? DEFAULT_MIN_CUE_S;
  const maxLines = opts.maxLines ?? 6;

  // An inverted window (end before start) is NORMALISED, not discarded. The
  // backend does the same: rejecting it would silently lose a real observation
  // because a third-party timestamp pair came back the wrong way round.
  const normalised = tags
    .filter((t) => Number.isFinite(t.start) && Number.isFinite(t.end))
    .map((t) => (t.end < t.start ? { ...t, start: t.end, end: t.start } : t));
  const usable = normalised.filter(
    (t) => t.confidence >= 0.6 && t.end - t.start >= minCue && t.end > t.start
  );
  if (!usable.length) {
    throw new Error("No video tags clear the confidence and duration floors");
  }

  const edges = Array.from(
    new Set(usable.flatMap((t) => [t.start, t.end]))
  ).sort((a, b) => a - b);

  const cues: string[] = [];
  for (let i = 0; i < edges.length - 1; i++) {
    const start = edges[i];
    const end = edges[i + 1];
    if (end - start < minCue) continue;
    const active = usable
      .filter((t) => t.start <= start + 1e-6 && t.end >= end - 1e-6)
      .map((t) => t.tag)
      .sort();
    if (!active.length) continue;
    // Dedupe: the same tag commonly spans two adjacent windows, and both are
    // "active" over the overlap, which rendered a cue reading "reeds / reeds".
    // A caption is not a multiset.
    const lines = Array.from(new Set(active)).slice(0, maxLines);
    cues.push(
      [
        String(cues.length + 1),
        `${formatTimestamp(start)} --> ${formatTimestamp(end)}`,
        ...lines.map(encodeCueText),
      ].join("\n")
    );
  }

  if (!cues.length) {
    throw new Error("Every interval fell below the minimum cue duration");
  }
  return `WEBVTT\n\n${cues.join("\n\n")}\n`;
}

/** Parse a VTT file back into cues. Used to VERIFY what was generated. */
export function parseVtt(vtt: string): Array<{
  start: number;
  end: number;
  lines: string[];
}> {
  const out: Array<{ start: number; end: number; lines: string[] }> = [];
  const blocks = vtt.trim().split(/\n\n+/);
  const toSeconds = (t: string) => {
    const m = t.match(/(\d{2}):(\d{2}):(\d{2})\.(\d{3})/);
    if (!m) throw new Error(`Unparseable timestamp: ${t}`);
    return (
      Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3]) + Number(m[4]) / 1000
    );
  };
  for (const block of blocks) {
    const lines = block.split("\n").filter(Boolean);
    if (!lines.length) continue;
    // The header is the only block that begins with WEBVTT, and it carries no
    // timing line. A cue block begins with its NUMBER. Skipping every block
    // that does not start with WEBVTT skipped every cue, which made this return
    // [] always -- and made validateVtt() report "no problems" about ANY track,
    // including a malformed one. A validator that inspects nothing is worse than
    // no validator, because it is trusted.
    if (lines[0].startsWith("WEBVTT")) continue;
    const body = lines;
    const timing = body.find((l) => l.includes("-->"));
    if (!timing) continue;
    const [a, b] = timing.split("-->").map((s) => s.trim());
    out.push({ start: toSeconds(a), end: toSeconds(b), lines: body.filter((l) => !l.includes("-->") && !/^\d+$/.test(l)) });
  }
  return out;
}

/**
 * Cue overlap and non-positive-duration check.
 *
 * Present in the frontend as well as the backend because the caption track is
 * rendered HERE; a malformed track must fail in the same test run that renders
 * it, not only in the Python suite.
 */
export function validateVtt(vtt: string): string[] {
  const problems: string[] = [];
  if (!vtt.startsWith("WEBVTT")) problems.push("missing WEBVTT header");
  let cues: Array<{ start: number; end: number; lines: string[] }> = [];
  try {
    cues = parseVtt(vtt);
  } catch (err) {
    return [...problems, (err as Error).message];
  }
  let previous: number | null = null;
  for (const cue of cues) {
    if (cue.end <= cue.start) {
      problems.push(`cue ends at or before it starts (${cue.start} -> ${cue.end})`);
    }
    if (previous !== null && cue.start < previous) {
      problems.push(`cue overlaps the previous one at ${cue.start}s`);
    }
    previous = cue.end;
  }
  return problems;
}

export { GAP_S };
