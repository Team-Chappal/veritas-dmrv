import { expect, test } from "./fixtures";

/**
 * CLS == 0 while figures change (rubric exit criterion).
 *
 * THE MEASUREMENT IS THE POINT, NOT THE MARKUP
 *
 * A ticker can reserve space in the markup and still shift: a web font
 * swapping in, an image without dimensions, a scrollbar appearing. So this
 * measures the browser's own `layout-shift` performance entries and asserts the
 * cumulative score is exactly zero. Asserting a CSS class exists would prove
 * nothing about what a reader experiences.
 *
 * The observer is installed BEFORE the first tick, and `hadRecentInput` is
 * filtered out, because a shift within 500ms of a click is excluded from CLS by
 * the specification -- leaving it in would let a shift hide behind a click.
 *
 * The ticker ticks on a 1.2s interval, so the test observes several ticks.
 */

const TICK_MS = 1200;

test.describe("live ticker does not shift layout", () => {
  test("cumulative layout shift is EXACTLY zero across several ticks", async ({ page }) => {
    // Install the observer first, and clear the buffer so early page-load shift
    // is not attributed to the ticker.
    await page.addInitScript(() => {
      const w = window as unknown as {
        __cls: number;
        __clsSources: string[];
      };
      w.__cls = 0;
      w.__clsSources = [];
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          const e = entry as PerformanceEntry & {
            hadRecentInput: boolean;
            value: number;
            sources?: Array<{ node?: Element | null }>;
          };
          if (e.hadRecentInput) continue;
          w.__cls += e.value;
          // NAME THE CULPRIT. A bare "0.0025" sends the reader hunting; this
          // is what turned "CLS is not zero" into "<video> has no intrinsic
          // size until its metadata loads" on the first attempt.
          for (const s of e.sources ?? []) {
            const el = s.node as HTMLElement | null;
            if (!el) continue;
            w.__clsSources.push(
              `${el.tagName.toLowerCase()}${
                el.className && typeof el.className === "string"
                  ? "." + el.className.split(/\s+/).slice(0, 2).join(".")
                  : ""
              }`
            );
          }
        }
      }).observe({ type: "layout-shift", buffered: true });
    });

    await page.goto("/console", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("metric-ticker")).toBeVisible();

    const first = await page.getByTestId("ticker-value-assets").innerText();
    // Several ticks. One tick could pass by luck; four cannot.
    await page.waitForTimeout(TICK_MS * 4 + 400);

    const { cls, sources } = await page.evaluate(() => {
      const w = window as unknown as { __cls: number; __clsSources: string[] };
      return { cls: w.__cls, sources: [...new Set(w.__clsSources)] };
    });
    const later = await page.getByTestId("ticker-value-assets").innerText();

    // The values must genuinely have changed, or "zero shift" is vacuous.
    expect(later, "ticker did not move, so zero CLS proves nothing").not.toBe(first);
    expect(Number(later.replace(/,/g, ""))).toBeGreaterThan(0);

    expect(
      cls,
      `cumulative layout shift was ${cls}, not 0. Culprits: ${
        sources.join(", ") || "none reported"
      }`
    ).toBe(0);
  });

  test("the strip's box is identical before and after a tick", async ({ page }) => {
    await page.goto("/console", { waitUntil: "domcontentloaded" });
    const grid = page.getByTestId("ticker-grid");
    const before = await grid.boundingBox();
    await page.waitForTimeout(TICK_MS * 2 + 300);
    const after = await grid.boundingBox();
    expect(after!.width).toBeCloseTo(before!.width, 1);
    expect(after!.height).toBeCloseTo(before!.height, 1);
  });

  test("figures use tabular numerals, so digits share an advance width", async ({ page }) => {
    await page.goto("/console", { waitUntil: "domcontentloaded" });
    const v = page.getByTestId("ticker-value-assets");
    const style = await v.evaluate((el) => getComputedStyle(el).fontVariantNumeric);
    expect(style).toMatch(/tabular-nums/);
  });

  test("width is RESERVED, not merely tabular", async ({ page }) => {
    // Tabular figures stop digits changing width; they do not stop a longer
    // number from needing more room. The min-width is what actually prevents
    // the reflow, so its presence is asserted.
    await page.goto("/console", { waitUntil: "domcontentloaded" });
    const reserved = await page
      .getByTestId("ticker-value-assets")
      .evaluate((el) => (el as HTMLElement).style.minWidth);
    expect(reserved).toMatch(/ch$/);
  });

  test("the video box EXISTS before its metadata does", async ({ page }) => {
    // Pins the actual defect rather than relying on the ticker test catching it
    // again. A <video> has no intrinsic size until its metadata arrives, so the
    // box used to be zero-height and then jump to 16:9 -- a layout shift of
    // 0.0025 that only appeared in CI, because it depends on how slow the
    // metadata is. The ratio is now reserved on the wrapper, so the box is the
    // right size immediately, whatever the network does.
    //
    // This spec navigates for itself: the describe block has no beforeEach and
    // its neighbours each carry their own `goto`, so without one here the page
    // was about:blank and the locator waited out the full 30s timeout -- which
    // said nothing whatsoever about the video.
    await page.goto("/console", { waitUntil: "domcontentloaded" });
    const wrapper = page.getByTestId("hotspot-frame");
    const box = await wrapper.boundingBox();
    expect(box!.height, "video wrapper has no height before metadata").toBeGreaterThan(20);

    const meta = await page
      .getByTestId("hotspot-video")
      .evaluate((el) => (el as HTMLVideoElement).readyState);
    // Whether or not metadata has landed yet, the box must already be right.
    const after = await wrapper.boundingBox();
    expect(after!.height).toBeCloseTo(box!.height, 1);
    // And it is a 16:9 box, not an arbitrary one.
    expect(box!.width / box!.height).toBeCloseTo(16 / 9, 1);
    void meta;
  });

  test("the ticker labels itself as a demonstration", async ({ page }) => {
    await page.goto("/console", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("ticker-source")).toContainText(/Demonstration/i);
  });
});
