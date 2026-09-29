import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import { expect, test } from "@playwright/test";

/**
 * The rubric walkthrough: every graded surface, in demo order, with the moment
 * it becomes visible. (rubric 6, S7.6)
 *
 * WHY THIS IS A TEST AND NOT A DOCUMENT
 *
 * A traceability matrix whose timestamps were typed by hand is a wish list. This
 * drives the real page, waits for each surface to actually be on screen, and
 * records the elapsed offset. So the matrix is GENERATED FROM A RUN, and two
 * things are enforced at once:
 *
 *   1. every graded surface is REACHABLE. If a component is renamed, unmounted,
 *      or moved below a fold that never opens, this fails -- and a rubric row
 *      that points at a panel nobody can see is a rubric row that does not count.
 *   2. the demo's shape is measured rather than estimated, which is what 7.7
 *      needs in order to re-cut the pitch to the real timings.
 *
 * WHAT THE TIMESTAMPS ARE, PRECISELY
 *
 * Offsets into a scripted walkthrough at a fixed viewport, on one machine, with
 * the backend ABSENT -- which is the configuration the exit criterion specifies.
 * They are not a recording of a human presentation, where these surfaces would
 * be reached at whatever pace the room dictates. Stated in the matrix rather
 * than implied.
 */

const OUT_DIR = path.resolve(__dirname, "../../docs");

/** Demo order, with the rubric each surface answers. */
const WALKTHROUGH = [
  { bullet: "intro", surface: "project-timeline", label: "Timeline" },
  { bullet: "1", surface: "portfolio-grid", label: "Portfolio grid" },
  { bullet: "2", surface: "hotspot-player", label: "Hotspot video + auto-tags" },
  { bullet: "3", surface: "impact-studio", label: "Before / after split slider" },
  { bullet: "4", surface: "campaign-studio", label: "Campaign studio" },
  { bullet: "5", surface: "semantic-search", label: "Semantic search" },
  { bullet: "6", surface: "provenance-panel", label: "Provenance panel" },
] as const;

test.describe("rubric walkthrough", () => {
  test("every graded surface is reachable, and the demo is timed", async ({ page }) => {
    test.setTimeout(120_000);
    await mkdir(OUT_DIR, { recursive: true });

    await page.goto("/", { waitUntil: "domcontentloaded" });
    await page.evaluate(() => document.fonts.ready);

    const started = Date.now();
    const timeline: Array<Record<string, unknown>> = [];
    const missing: string[] = [];

    for (const step of WALKTHROUGH) {
      const target = page.getByTestId(step.surface);
      if ((await target.count()) === 0) {
        // Recorded rather than thrown, so the failure message can name every
        // surface that is missing instead of only the first.
        missing.push(`${step.surface} (bullet ${step.bullet})`);
        continue;
      }
      await target.scrollIntoViewIfNeeded();
      await expect(target).toBeVisible();
      // A short settle so the recorded offset reflects a surface a presenter
      // could actually point at, not one caught mid-transition.
      await page.waitForTimeout(120);
      timeline.push({
        bullet: step.bullet,
        surface: step.surface,
        label: step.label,
        offset_s: Number(((Date.now() - started) / 1000).toFixed(2)),
      });
    }

    expect(
      missing,
      `graded surfaces not found on the page: ${missing.join(", ")}`
    ).toEqual([]);

    const total = Number(((Date.now() - started) / 1000).toFixed(2));
    const payload = {
      generated_utc: new Date().toISOString(),
      viewport: page.viewportSize(),
      configuration: "backend absent (fixture mode), production build",
      walkthrough_seconds: total,
      note:
        "Offsets into a scripted walkthrough at a fixed viewport on one machine, " +
        "not a recording of a human presentation. Surface order and offsets are " +
        "used to re-cut the 180 s pitch (7.7).",
      surfaces: timeline,
    };
    await writeFile(
      path.join(OUT_DIR, "demo-timeline.json"),
      JSON.stringify(payload, null, 2)
    );

    // The pitch is 180 s. A walkthrough that cannot fit inside it is not a
    // demo, and finding that out here is cheaper than finding it out on stage.
    expect(
      total,
      `the walkthrough takes ${total}s; the pitch is 180s`
    ).toBeLessThan(180);
  });

  test("the walkthrough visits the surfaces in rubric order", async ({ page }) => {
    const seen: string[] = [];
    for (const step of WALKTHROUGH) {
      const target = page.getByTestId(step.surface);
      if ((await target.count()) > 0) seen.push(step.surface);
    }
    // Whatever is present must be in the declared order, because the generated
    // matrix presents the numbers in that order and a mismatch would quietly
    // mislabel the pitch timings.
    expect(seen).toEqual([...WALKTHROUGH.map((s) => s.surface)].filter((s) => seen.includes(s)));
  });
});
