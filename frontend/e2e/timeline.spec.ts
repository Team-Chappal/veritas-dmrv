import { expect, test } from "./fixtures";

import { DEMO_SUMMARY, DEMO_TIMELINE } from "@/lib/project-fixture";

/**
 * ProjectTimeline and SummaryCard — rubric intro and bullet 4.
 *
 * The assertions that carry weight are the ones about MISSING evidence. A
 * timeline fixture where every epoch is complete would pass every "is it
 * rendered" check while demonstrating nothing, so month-18 has no captures at
 * all and month-6 is short by one — and the specs require the component to show
 * both.
 */

test.describe("ProjectTimeline", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/console", { waitUntil: "domcontentloaded" });
  });

  test("renders every epoch in schedule order", async ({ page }) => {
    const epochs = page.getByTestId("epoch");
    await expect(epochs).toHaveCount(DEMO_TIMELINE.epochs.length);
    const labels = await epochs.evaluateAll((els) =>
      els.map((e) => e.getAttribute("data-status"))
    );
    expect(labels).toEqual(DEMO_TIMELINE.epochs.map((e) => e.status));
  });

  test("states the coverage shortfall BEFORE the timeline", async ({ page }) => {
    // A reviewer who must scroll to discover the shortfall has already formed
    // the wrong impression of the project.
    const coverage = page.getByTestId("coverage-pct");
    await expect(coverage).toBeVisible();
    await expect(coverage).toHaveText(`${DEMO_TIMELINE.coverage_pct.toFixed(1)}%`);
    await expect(page.getByTestId("coverage-status")).toContainText(
      /no captures at all/i
    );
  });

  test("coverage is not rounded up to 100", async ({ page }) => {
    const shown = Number(
      (await page.getByTestId("coverage-pct").innerText()).replace("%", "")
    );
    expect(shown).toBeLessThan(100);
    expect(shown).toBe(DEMO_TIMELINE.coverage_pct);
  });

  test("an epoch with NO captures is listed, not omitted", async ({ page }) => {
    // Omitting it would close the gap in the picture while leaving it open in
    // the data, which is the specific dishonesty this component avoids.
    const missing = page.locator('[data-status="missing"]');
    await expect(missing).toHaveCount(1);
    await expect(missing).toContainText("Not captured");
  });

  test("the gap list names both the shortfall and the schedule date", async ({ page }) => {
    await expect(page.getByTestId("gap-item")).toHaveCount(DEMO_TIMELINE.gaps.length);
    const first = page.getByTestId("gap-item").first();
    await expect(first).toContainText(/short by \d+/i);
    await expect(first).toContainText(/due \d{4}-\d{2}-\d{2}/);
  });

  test("a missing gap is distinguished from a partial one", async ({ page }) => {
    await expect(page.locator('[data-severity="missing"]')).toHaveCount(1);
    await expect(page.locator('[data-severity="partial"]')).toHaveCount(1);
  });

  test("a missing epoch shows a blank capture date, not a fabricated one", async ({ page }) => {
    await page.getByTestId("epoch-toggle-progress_month_18").click();
    const detail = page.getByTestId("epoch-detail");
    // Scope to the CAPTURE field. My first version asserted the whole panel did
    // not contain the scheduled date, which was wrong: showing when the epoch
    // was DUE is the point. What must not appear is a fabricated CAPTURE date.
    const captureDate = detail
      .locator("div")
      .filter({ hasText: "First capture" })
      .locator("dd");
    await expect(captureDate).toHaveText("— none —");
    // And the scheduled date IS shown, because the gap is about the schedule.
    await expect(detail).toContainText("2026-03-15");
    await expect(detail).toContainText("3 / 0");
  });

  test("epochs expand and collapse", async ({ page }) => {
    const toggle = page.getByTestId("epoch-toggle-baseline_month_0");
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByTestId("epoch-detail")).toBeVisible();
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  test("no status is signalled by colour alone", async ({ page }) => {
    // A missing epoch reads differently in greyscale because of the glyph and
    // the word, not the hue.
    await expect(page.locator('[data-status="missing"]')).toContainText("✖");
    await expect(page.locator('[data-status="missing"]')).toContainText(
      "Not captured"
    );
    await expect(page.locator('[data-status="FULL"]').first()).toContainText(
      "Fully captured"
    );
  });

  test("the longest gap is reported, so it cannot be reframed as a short project", async ({ page }) => {
    await expect(page.getByTestId("project-timeline")).toContainText(
      `Longest gap ${DEMO_TIMELINE.longest_gap_months} months`
    );
  });
});

test.describe("SummaryCard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/console", { waitUntil: "domcontentloaded" });
  });

  test("every figure links to a source", async ({ page }) => {
    const figures = page.getByTestId("summary-figure");
    await expect(figures).toHaveCount(4);
    const sources = page.getByTestId("summary-source");
    await expect(sources).toHaveCount(4);
    for (let i = 0; i < 4; i++) {
      await expect(sources.nth(i)).toHaveAttribute("href", /#/);
      // The screen-reader text carries WHY this figure is what it is.
      await expect(sources.nth(i)).toHaveAttribute("title", /.+|null/);
    }
  });

  test("the VM0047 explanation is attached to the carbon figure", async ({ page }) => {
    // 8.7% sampling error is BELOW the 15% threshold, so net == gross. That
    // looks like a missing multiplication and has to be explained where the
    // number is, not in a footnote.
    const link = page.getByTestId("summary-source").nth(1);
    await expect(link).toHaveAttribute("title", /15% discount threshold/i);
  });

  test("states that no language model was involved", async ({ page }) => {
    await expect(page.getByTestId("summary-grounded")).toContainText("Grounded");
    await expect(page.getByTestId("project-timeline")).toContainText(
      /no language model involved/i
    );
  });

  test("quarantined assets are surfaced on the asset figure", async ({ page }) => {
    const assets = page.getByTestId("summary-figure").nth(3);
    await expect(assets).toContainText(
      `${DEMO_SUMMARY.facts.quarantined_assets} quarantined`
    );
  });

  test("figures are tabular, so digits align for comparison", async ({ page }) => {
    const style = await page
      .getByTestId("summary-figure")
      .first()
      .locator("dd")
      .evaluate((el) => getComputedStyle(el).fontVariantNumeric);
    expect(style).toMatch(/tabular-nums/);
  });

  test("the summary text agrees with the figures", async ({ page }) => {
    // A prose summary that contradicts its own numbers is worse than none.
    await expect(page.getByTestId("project-timeline")).toContainText("38.2%");
    await expect(page.getByTestId("project-timeline")).toContainText("8.7%");
  });
});
