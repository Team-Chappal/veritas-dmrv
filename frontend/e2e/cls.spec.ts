import { expect, test } from "@playwright/test";

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
      (window as unknown as { __cls: number }).__cls = 0;
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          const e = entry as PerformanceEntry & {
            hadRecentInput: boolean;
            value: number;
          };
          if (e.hadRecentInput) continue;
          (window as unknown as { __cls: number }).__cls += e.value;
        }
      }).observe({ type: "layout-shift", buffered: true });
    });

    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("metric-ticker")).toBeVisible();

    const first = await page.getByTestId("ticker-value-assets").innerText();
    // Several ticks. One tick could pass by luck; four cannot.
    await page.waitForTimeout(TICK_MS * 4 + 400);

    const cls = await page.evaluate(() => (window as unknown as { __cls: number }).__cls);
    const later = await page.getByTestId("ticker-value-assets").innerText();

    // The values must genuinely have changed, or "zero shift" is vacuous.
    expect(later, "ticker did not move, so zero CLS proves nothing").not.toBe(first);
    expect(Number(later.replace(/,/g, ""))).toBeGreaterThan(0);

    expect(cls, `cumulative layout shift was ${cls}, not 0`).toBe(0);
  });

  test("the strip's box is identical before and after a tick", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const grid = page.getByTestId("ticker-grid");
    const before = await grid.boundingBox();
    await page.waitForTimeout(TICK_MS * 2 + 300);
    const after = await grid.boundingBox();
    expect(after!.width).toBeCloseTo(before!.width, 1);
    expect(after!.height).toBeCloseTo(before!.height, 1);
  });

  test("figures use tabular numerals, so digits share an advance width", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const v = page.getByTestId("ticker-value-assets");
    const style = await v.evaluate((el) => getComputedStyle(el).fontVariantNumeric);
    expect(style).toMatch(/tabular-nums/);
  });

  test("width is RESERVED, not merely tabular", async ({ page }) => {
    // Tabular figures stop digits changing width; they do not stop a longer
    // number from needing more room. The min-width is what actually prevents
    // the reflow, so its presence is asserted.
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const reserved = await page
      .getByTestId("ticker-value-assets")
      .evaluate((el) => (el as HTMLElement).style.minWidth);
    expect(reserved).toMatch(/ch$/);
  });

  test("the ticker labels itself as a demonstration", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("ticker-source")).toContainText(/Demonstration/i);
  });
});
