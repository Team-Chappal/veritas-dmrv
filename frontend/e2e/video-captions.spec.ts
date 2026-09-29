import { expect, test } from "./fixtures";

import { DEMO_ANALYSIS } from "@/lib/video-fixture";
import { buildVtt, formatTimestamp, parseVtt, validateVtt } from "@/lib/video";

/**
 * Caption-track generation, verified as a MEDIA FILE rather than as strings.
 *
 * The failure mode this exists for is silent: overlapping cues are invalid VTT,
 * and a naive gap-fill over nested windows produces a NEGATIVE duration that a
 * player may render as a blank or an infinite cue. Parsing the generated track
 * back and measuring the intervals is the only way to see it.
 */

test.describe("WebVTT generation", () => {
  test("the generated track is valid", () => {
    expect(validateVtt(DEMO_ANALYSIS.vtt)).toEqual([]);
  });

  test("no cue overlaps another", () => {
    const cues = parseVtt(DEMO_ANALYSIS.vtt);
    for (let i = 1; i < cues.length; i++) {
      expect(
        cues[i].start,
        `cue ${i + 1} starts at ${cues[i].start}s, before the previous ends at ${cues[i - 1].end}s`
      ).toBeGreaterThanOrEqual(cues[i - 1].end);
    }
  });

  test("no cue has zero or negative duration", () => {
    for (const cue of parseVtt(DEMO_ANALYSIS.vtt)) {
      expect(cue.end).toBeGreaterThan(cue.start);
    }
  });

  test("NESTED windows become one cue with several LINES, not two cues", () => {
    // Cloudinary returns a `canopy`-inside-`forest` shape. Emitting two
    // overlapping cues is invalid; dropping the inner one loses an
    // observation. Multiple lines in one cue is the only correct answer.
    const multi = parseVtt(DEMO_ANALYSIS.vtt).filter((c) => c.lines.length > 1);
    expect(multi.length).toBeGreaterThan(0);
    expect(
      multi.some((c) => c.lines.includes("elephant") && c.lines.includes("wetland"))
    ).toBe(true);
  });

  test("every observation survives the sweep", () => {
    const text = DEMO_ANALYSIS.vtt;
    for (const tag of ["open_water", "wetland", "elephant", "reeds", "shoreline", "low_light"]) {
      expect(text, `${tag} was dropped`).toContain(tag);
    }
  });

  test("confidence and duration floors are applied", () => {
    expect(() =>
      buildVtt([{ tag: "noise", start: 0, end: 9, confidence: 0.2 }])
    ).toThrow(/confidence|duration/i);
    expect(() =>
      buildVtt([{ tag: "blip", start: 1, end: 1.1, confidence: 0.95 }])
    ).toThrow(/duration/i);
  });

  test("an inverted window is normalised, not emitted", () => {
    const vtt = buildVtt([{ tag: "x", start: 10, end: 2, confidence: 0.9 }]);
    const cue = parseVtt(vtt)[0];
    expect(cue.end).toBeGreaterThan(cue.start);
  });

  test("a cue arrow inside a tag cannot break the track", () => {
    const vtt = buildVtt([{ tag: "a-->b", start: 0, end: 9, confidence: 0.9 }]);
    expect(validateVtt(vtt)).toEqual([]);
  });

  test("timestamps round-trip", () => {
    for (const s of [0, 1.5, 61.2, 3661.5]) {
      const cue = parseVtt(
        buildVtt([{ tag: "t", start: s, end: s + 1, confidence: 0.9 }])
      )[0];
      expect(cue.start).toBeCloseTo(s, 2);
    }
  });

  test("a bad total cannot produce a negative field", () => {
    expect(formatTimestamp(-5)).toBe("00:00:00.000");
    expect(formatTimestamp(NaN)).toBe("00:00:00.000");
  });

  test("the validator CATCHES a malformed track", () => {
    // The reason this test exists. parseVtt used to skip every cue block, so it
    // always returned [] and validateVtt reported "no problems" about ANY input
    // -- including a header-only file and a file with overlapping cues. A
    // validator that inspects nothing gets trusted, which is worse than having
    // none. Each case below must be REJECTED.
    // NOTE: a cue-less track is LEGAL VTT, so validateVtt is right to report no
    // problem with one. Asserting otherwise would be the same class of error as
    // the vacuous validator -- a test stating a rule that is not true. What
    // matters is that the GENERATOR refuses to produce an empty track, below.

    const overlapping =
      "WEBVTT\n\n1\n00:00:00.000 --> 00:00:05.000\na\n\n" +
      "2\n00:00:02.000 --> 00:00:07.000\nb\n";
    expect(
      validateVtt(overlapping).some((p) => /overlap/i.test(p)),
      "overlapping cues must be reported"
    ).toBe(true);

    const inverted = "WEBVTT\n\n1\n00:00:05.000 --> 00:00:01.000\na\n";
    expect(
      validateVtt(inverted).some((p) => /ends at or before/i.test(p)),
      "a non-positive duration must be reported"
    ).toBe(true);

    const noHeader = "1\n00:00:00.000 --> 00:00:01.000\na\n";
    expect(validateVtt(noHeader).some((p) => /WEBVTT header/i.test(p))).toBe(true);

    expect(validateVtt("WEBVTT\n\n1\nxx --> yy\na\n").length).toBeGreaterThan(0);
  });

  test("the generator refuses to emit an empty or all-floored track", () => {
    // The validator being lenient about a cue-less file is fine; the generator
    // must never be the reason one exists.
    expect(() => buildVtt([])).toThrow();
    expect(() =>
      buildVtt([{ tag: "a", start: 0, end: 9, confidence: 0.99 }], { minCueSeconds: 30 })
    ).toThrow();
  });

  test("a caption never shows the same tag twice", () => {
    // The fixture has `reeds` in two adjacent windows, so both are "active"
    // across the overlap. Before the dedupe that rendered a cue reading
    // "reeds / reeds" -- a caption is not a multiset.
    for (const cue of parseVtt(DEMO_ANALYSIS.vtt)) {
      expect(new Set(cue.lines).size, `duplicate line in cue: ${cue.lines.join(" / ")}`).toBe(
        cue.lines.length
      );
    }
  });

  test("the validator is not vacuous on a good track either", () => {
    // Sanity in the other direction: a well-formed track reports no problems,
    // so the passing assertions above are not the validator being lenient.
    expect(validateVtt(DEMO_ANALYSIS.vtt)).toEqual([]);
    expect(parseVtt(DEMO_ANALYSIS.vtt).length).toBeGreaterThan(3);
  });

  test("generation is deterministic", () => {
    expect(buildVtt(DEMO_ANALYSIS.tags)).toBe(DEMO_ANALYSIS.vtt);
  });
});
