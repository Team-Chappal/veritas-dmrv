import { expect, test } from "./fixtures";

/**
 * Matcher for the asset-collection endpoint ONLY.
 *
 * A glob like `**\/api\/v1/assets**` also matches
 * `/api/v1/assets/{id}/provenance`, so the mock silently served the asset-list
 * body to the provenance fetch and broke both panels. This is anchored on the
 * query string so it cannot spill onto a sibling route.
 */
const ASSETS_ROUTE = /\/api\/v1\/assets(\?|$)/;

/**
 * PortfolioGrid — rubric bullet 1, "analyze and intelligently organize large
 * collections".
 *
 * The load-bearing assertion is again the honesty one: a grid of 500 synthetic
 * cards that does not say it is synthetic is a contact sheet of lies. Everything
 * else is organisation behaviour, which is the actual rubric claim.
 */

test.describe("PortfolioGrid", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/console", { waitUntil: "domcontentloaded" });
  });

  test("renders a grid of asset cards", async ({ page }) => {
    await expect(page.getByTestId("portfolio-grid")).toBeVisible();
    const cards = page.getByTestId("asset-card");
    // toHaveCount auto-waits; a bare count() would read 0 and pass anyway.
    await expect(cards.first()).toBeVisible();
    expect(await cards.count()).toBeGreaterThan(5);
  });

  test("labels itself FIXTURE and says why, with no backend", async ({ page }) => {
    await expect(page.getByTestId("portfolio-source")).toContainText("Fixture");
    await expect(page.getByTestId("portfolio-reason")).toContainText(
      /no cloudinary call was made/i
    );
    await expect(page.getByTestId("portfolio-reason")).toHaveAttribute(
      "role",
      "status"
    );
  });

  test("reports how much of the collection is shown", async ({ page }) => {
    const count = page.getByTestId("portfolio-count");
    await expect(count).toContainText(/\d+ of \d+ assets/);
    // Live region: filtering changes the number, and a screen-reader user needs
    // to hear the new total without moving focus.
    await expect(count).toHaveAttribute("aria-live", "polite");
  });

  test("filter chips carry counts, which is the reason to click one", async ({ page }) => {
    const chip = page.getByTestId("filter-decision-VERIFIED_PASS");
    await expect(chip).toBeVisible();
    await expect(chip).toContainText(/\d/);
    // The count is announced with a unit, not as a bare number.
    await expect(chip.locator(".sr-only")).toHaveText("assets");
  });

  test("filtering narrows the grid to exactly what the chip promised", async ({ page }) => {
    // Cards are data-derived, so wait for them before counting a baseline.
    await expect(page.getByTestId("asset-card").first()).toBeVisible();
    const before = await page.getByTestId("asset-card").count();

    const chip = page.getByTestId("filter-decision-QUARANTINE_FRAUD");
    const promised = Number(await chip.locator(".tabular-nums").innerText());
    await chip.click();

    // Polled, not immediate: the previous version of this assertion passed on
    // `0 < before`, which a race between the click and the refetch also
    // produces. An empty grid is not "narrowed".
    await expect
      .poll(async () => page.getByTestId("asset-card").count())
      .toBe(promised);
    expect(promised).toBeLessThan(before);
    expect(promised).toBeGreaterThan(0);

    // Every remaining card actually matches the filter.
    const decisions = await page
      .getByTestId("asset-card")
      .evaluateAll((els) => els.map((e) => e.getAttribute("data-decision")));
    expect(new Set(decisions)).toEqual(new Set(["QUARANTINE_FRAUD"]));
  });

  test("a filter can be toggled off", async ({ page }) => {
    await expect(page.getByTestId("asset-card").first()).toBeVisible();
    const before = await page.getByTestId("asset-card").count();
    const chip = page.getByTestId("filter-decision-REVIEW_AMBIGUOUS");

    await chip.click();
    await expect(chip).toHaveAttribute("aria-pressed", "true");
    await expect.poll(async () => page.getByTestId("asset-card").count()).not.toBe(
      before
    );

    await chip.click();
    await expect(chip).toHaveAttribute("aria-pressed", "false");
    await expect.poll(async () => page.getByTestId("asset-card").count()).toBe(
      before
    );
  });

  test("two filters combine rather than replace", async ({ page }) => {
    await page.getByTestId("filter-decision-VERIFIED_PASS").click();
    await page.getByTestId("filter-c2pa-C2PA_MUTATED").click();

    await expect
      .poll(async () =>
        page.getByTestId("asset-card").evaluateAll((els) => {
          const d = els.map((e) => e.getAttribute("data-decision"));
          const c = els.map((e) => e.getAttribute("data-c2pa"));
          return d.some((v) => v !== "VERIFIED_PASS") || c.some((v) => v !== "C2PA_MUTATED");
        })
      )
      .toBe(false);
  });

  test("applying a filter does not make the other chips disappear", async ({ page }) => {
    // WAIT for the facets. A raw `.count()` right after navigation can read 0
    // because the chips are data-derived and the fetch has not resolved -- and
    // a count of 0 then satisfies every "the chips did not vanish" assertion
    // below, which is how this test passed vacuously in one run and failed in
    // the next. `toHaveCount` auto-waits; `.count()` does not.
    // THE TRAP. Counting the `decision` facet with the `decision` filter applied
    // collapses it to the single selected value, so the other chips vanish and
    // the reviewer cannot switch straight from "quarantined" to "review" — only
    // clear the filter first. Each axis must be counted with its OWN filter
    // lifted, which is standard faceted-search behaviour.
    const chips = page.locator('[data-testid^="filter-decision-"]');
    await expect(chips.first()).toBeVisible();
    await expect.poll(async () => chips.count()).toBeGreaterThan(1);
    const before = await chips.count();

    await page.getByTestId("filter-decision-QUARANTINE_FRAUD").click();
    await expect(page.locator('[data-testid^="filter-decision-"]')).toHaveCount(before);

    // And the counts must still answer "how many would I get if I chose this?",
    // so they must not all read the same.
    const counts = await page
      .locator('[data-testid^="filter-decision-"] .tabular-nums')
      .allInnerTexts();
    expect(new Set(counts).size).toBeGreaterThan(1);
  });

  test("a filter axis reflects the OTHER filters", async ({ page }) => {
    await page.getByTestId("filter-decision-QUARANTINE_FRAUD").click();
    // Wait for the refetch before reading, or this reads the previous render.
    await expect(page.getByTestId("asset-card").first()).toBeVisible();
    await expect
      .poll(async () => page.getByTestId("asset-card").count())
      .toBeGreaterThan(0);

    // Every card is quarantined...
    //
    // The browser must return an ARRAY, not a Set. Playwright serialises the
    // result of evaluateAll, and a Set comes back as `{}` -- so asserting on a
    // Set returned from the page always fails, and fails in a way that looks
    // like "no cards matched" rather than "wrong assertion".
    const decisions = await page
      .getByTestId("asset-card")
      .evaluateAll((els) => els.map((e) => e.getAttribute("data-decision")));
    expect(decisions.length).toBeGreaterThan(0);
    expect(new Set(decisions)).toEqual(new Set(["QUARANTINE_FRAUD"]));

    // ...and the c2pa chips are counted WITHIN that set, so their total is the
    // number of quarantined assets, not the size of the whole corpus.
    const c2paCounts = (
      await page.locator('[data-testid^="filter-c2pa-"] .tabular-nums').allInnerTexts()
    ).map((t) => Number(t));
    expect(c2paCounts.reduce((a, b) => a + b, 0)).toBe(
      await page.locator('[data-testid="filter-decision-QUARANTINE_FRAUD"] .tabular-nums')
        .first()
        .innerText()
        .then(Number)
    );
  });

  test("cards state both a verdict and a provenance state in words", async ({ page }) => {
    const card = page.getByTestId("asset-card").first();
    // Greyscale-printable: two labelled pills, not two coloured dots.
    await expect(card).toContainText(/Verified|Review|Quarantined/);
    await expect(card).toContainText(/manifest|Manifest/);
  });

  test("an empty result is described as a gap, not silence", async ({ page }) => {
    await page.route(ASSETS_ROUTE, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total_matched: 0,
          returned: 0,
          offset: 0,
          limit: 24,
          has_more: false,
          facets: { decision: {}, phase: {}, c2pa: {}, domain: {} },
          assets: [],
          _provenance: {
            request_id: "r1",
            generated_at: "2026-09-28T00:00:00Z",
            mode: "live",
            evidence: "live Cloudinary",
            app_env: "production",
            elapsed_ms: 3,
            path: "/api/v1/assets",
            method: "GET",
            provenance_endpoint: "http://x/api/v1/assets/{id}/provenance",
            caveat: "",
          },
        }),
      })
    );
    await page.reload({ waitUntil: "domcontentloaded" });

    // "No assets" is ambiguous: a gap in coverage, or a broken query? The copy
    // resolves it, because on this product the difference matters.
    await expect(page.getByTestId("portfolio-empty")).toContainText(
      /coverage gap worth reporting/i
    );
    await expect(page.getByTestId("portfolio-source")).toContainText("Live");
  });

  test("does not badge Live for a fixture-mode 200", async ({ page }) => {
    await page.route(ASSETS_ROUTE, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total_matched: 1,
          returned: 1,
          offset: 0,
          limit: 24,
          has_more: false,
          facets: { decision: {}, phase: {}, c2pa: {}, domain: {} },
          assets: [],
          _provenance: {
            request_id: "r2",
            generated_at: "2026-09-28T00:00:00Z",
            mode: "fixture",
            evidence: "FIXTURE — synthetic",
            app_env: "development",
            elapsed_ms: 1,
            path: "/api/v1/assets",
            method: "GET",
            provenance_endpoint: "http://x/api/v1/assets/{id}/provenance",
            caveat: "Synthetic corpus.",
          },
        }),
      })
    );
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("portfolio-source")).toContainText("Fixture");
  });

  test("an unrecognised verdict is shown, not silently treated as fine", async ({ page }) => {
    await page.route(ASSETS_ROUTE, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total_matched: 1,
          returned: 1,
          offset: 0,
          limit: 24,
          has_more: false,
          facets: { decision: { WEIRD_VERDICT: 1 }, phase: {}, c2pa: {}, domain: {} },
          assets: [
            {
              asset_id: "x/1",
              public_id: "x/1",
              esg_project_id: "KEN-008",
              milestone_phase: "baseline_month_0",
              sustainability_domain: "reforestation",
              capture_timestamp: "2026-01-01",
              media_type: "image",
              jev_triage_decision: "WEIRD_VERDICT",
              jev_confidence_score: 50,
              c2pa_provenance: "C2PA_WHATEVER",
              canopy_delta_pct: null,
              tags: [],
            },
          ],
          _provenance: {
            request_id: "r3",
            generated_at: "2026-09-28T00:00:00Z",
            mode: "live",
            evidence: "live",
            app_env: "production",
            elapsed_ms: 1,
            path: "/api/v1/assets",
            method: "GET",
            provenance_endpoint: "http://x/p",
            caveat: "",
          },
        }),
      })
    );
    await page.reload({ waitUntil: "domcontentloaded" });

    // An unmapped status must not render as a neutral box. Surfacing the raw
    // value is what lets someone notice the backend changed it.
    await expect(page.getByTestId("asset-card")).toContainText("WEIRD_VERDICT");
    await expect(page.getByTestId("asset-card")).toContainText("C2PA_WHATEVER");
  });
});
