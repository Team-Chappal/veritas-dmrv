import { expect, test } from "@playwright/test";

/**
 * SemanticSearch — rubric bullet 5.
 *
 * The distinguishing specs are the ones about ABSENCE. A search UI that only
 * reports hits is easy to build and quietly misleading; the tests that matter
 * here are that unmatched terms are surfaced, and that the engine's limitation is
 * stated rather than paraphrased away.
 */

test.describe("SemanticSearch", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
  });

  async function search(page: import("@playwright/test").Page, q: string) {
    await page.getByTestId("search-input").fill(q);
    await page.getByTestId("search-submit").click();
  }

  test("returns hits for a query", async ({ page }) => {
    await search(page, "canopy");
    await expect(page.getByTestId("search-hits").locator("li")).not.toHaveCount(0);
    await expect(page.getByTestId("search-count")).toContainText(/engine:/);
  });

  test("names the engine that answered, not a generic 'AI'", async ({ page }) => {
    await search(page, "canopy");
    // The honest label. Saying "AI search" over a tf-idf index is the exact
    // overclaim this project is organised against.
    await expect(page.getByTestId("search-count")).toContainText("tfidf_lexical");
  });

  test("states the engine's limitation, unedited", async ({ page }) => {
    await search(page, "canopy");
    const notes = page.getByTestId("search-notes");
    await expect(notes).toBeVisible();
    await expect(notes).toContainText(/lexical|lexically/i);
    // The specific consequence, not a vague disclaimer.
    await expect(notes).toContainText(/synonym/i);
  });

  test("surfaces query terms that matched NOTHING", async ({ page }) => {
    await search(page, "canopy zzzznotatag");
    const unmatched = page.getByTestId("search-unmatched");
    await expect(unmatched).toBeVisible();
    await expect(unmatched).toContainText('"zzzznotatag"');
    // And it must be announced, and must distinguish "not in the index" from
    // "no evidence exists" — those are different findings.
    await expect(unmatched).toHaveAttribute("role", "status");
    await expect(unmatched).toContainText(/not the same as/i);
  });

  test("shows no unmatched banner when every term matched", async ({ page }) => {
    await search(page, "canopy");
    await expect(page.getByTestId("search-unmatched")).toHaveCount(0);
  });

  test("shows which terms each hit matched", async ({ page }) => {
    await search(page, "canopy");
    const hit = page.getByTestId("search-hit").first();
    await expect(hit).toContainText(/Matched/i);
    await expect(hit).toContainText("canopy");
  });

  test("tag chips run a search", async ({ page }) => {
    const chip = page.locator('[data-testid^="search-tag-"]').first();
    const tag = (await chip.innerText()).trim();
    await chip.click();
    await expect(page.getByTestId("search-input")).toHaveValue(tag);
    await expect(page.getByTestId("search-hits").locator("li")).not.toHaveCount(0);
  });

  test("a term the lexical engine cannot relate is reported, not silently dropped", async ({ page }) => {
    // 'tree' should not find 'canopy'. If a future index becomes semantic this
    // test should change, and the comment is where that change is recorded.
    await search(page, "tree");
    await expect(page.getByTestId("search-unmatched")).toContainText('"tree"');
  });

  test("an empty result says so without blaming the collection", async ({ page }) => {
    await search(page, "zzzznotatag");
    await expect(page.getByTestId("search-empty")).toBeVisible();
    await expect(page.getByTestId("search-empty")).toContainText(/absent from the index/i);
  });

  test("labels itself FIXTURE with no backend", async ({ page }) => {
    await search(page, "canopy");
    await expect(page.getByTestId("search-source")).toContainText("Fixture");
    await expect(page.getByTestId("search-reason")).toContainText(
      /no cloudinary call was made/i
    );
  });

  test("does not badge Live for a fixture-mode 200", async ({ page }) => {
    // The transport succeeded and the index was local. Same rule as every other
    // surface: read _provenance.mode, do not trust the status code.
    await page.route(/\/api\/v1\/search(\?|$)/, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          query: "canopy",
          backend: "tfidf_lexical",
          total_indexed: 1,
          count: 0,
          hits: [],
          unmatched_terms: ["canopy"],
          notes: "local",
          _provenance: {
            request_id: "r1",
            generated_at: "2026-09-28T00:00:00Z",
            mode: "fixture",
            evidence: "FIXTURE",
            app_env: "development",
            elapsed_ms: 1,
            path: "/api/v1/search",
            method: "GET",
            provenance_endpoint: "x",
            caveat: "Local index.",
          },
        }),
      })
    );
    await page.reload({ waitUntil: "domcontentloaded" });
    await search(page, "canopy");
    await expect(page.getByTestId("search-source")).toContainText("Fixture");
  });

  test("an empty query searches nothing rather than everything", async ({ page }) => {
    await search(page, "");
    await expect(page.getByTestId("search-hits")).toHaveCount(0);
    await expect(page.getByTestId("search-count")).toHaveCount(0);
  });

  test("the search box is reachable and labelled", async ({ page }) => {
    await expect(page.getByLabel(/search evidence by keyword or tag/i)).toBeVisible();
    await expect(page.getByRole("search")).toBeVisible();
  });

  test("an unmatched term PENALISES the score, as the real backend does", async ({ page }) => {
    // The fixture originally reported ~0.9999 for a query where half the terms
    // matched nothing, because it normalised over query terms the index has
    // never seen. The backend gives an unknown term idf 1.0, which inflates the
    // query vector and shrinks the cosine -- so "canopy zzzz" scores BELOW
    // "canopy" alone there too. A fixture that flattered itself would make a
    // half-failed query look like a certain match.
    // POLLED, not read once. Submitting is async, so an immediate read returns
    // the PREVIOUS query's results -- which made this spec compare 0.367 with
    // 0.367 and fail for a reason that had nothing to do with the scorer.
    const topScore = async (q: string) => {
      await search(page, q);
      await expect(page.getByTestId("search-hits").locator("li")).not.toHaveCount(0);
      // Wait on the query the RESULTS came from, not the one that is typed.
      // data-query updates the moment submit is pressed, which is before the
      // fetch resolves, so waiting on it still reads the previous results.
      await expect(page.getByTestId("semantic-search")).toHaveAttribute(
        "data-result-query",
        q
      );
      return Number(
        await page.getByTestId("search-hit").first().locator(".text-telemetry").innerText()
      );
    };

    const one = await topScore("canopy");
    const two = await topScore("canopy mangrove");
    const penalised = await topScore("canopy zzzznotatag");

    // More matched terms scores higher.
    expect(two).toBeGreaterThan(one);
    // An unmatched term drags the score DOWN, not up.
    expect(penalised).toBeLessThan(one);
    // And a real tf-idf cosine for a single common term is nowhere near 1.0.
    // A 0.999 reads as "certain match", which tf-idf cannot support.
    expect(one).toBeLessThan(0.9);
    expect(one).toBeGreaterThan(0);
  });

  test("the score is labelled as relevance, not confidence", async ({ page }) => {
    await search(page, "canopy");
    const score = page.getByTestId("search-hit").first().locator(".text-telemetry");
    // A tf-idf score presented as a percentage would be read as "94% sure",
    // which is a different and much stronger claim than it supports.
    await expect(score).toHaveAttribute("title", /not a confidence/i);
  });
});
