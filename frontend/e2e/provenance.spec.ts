import { expect, test } from "./fixtures";

/**
 * ProvenancePanel — rubric bullet 6.
 *
 * The tests that matter are the degradation ones. A provenance panel that shows
 * bundled data with the same confidence as measured data is worse than no
 * panel, so "does it LABEL itself when it is faking" is the load-bearing
 * assertion here, not "does it render".
 *
 * No backend is started. Every case below runs with the API unreachable, which
 * is the normal state on stage.
 */

test.describe("ProvenancePanel", () => {
  test("renders the master asset and its hash", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });

    const panel = page.getByTestId("provenance-panel");
    await expect(panel).toBeVisible();
    await expect(page.getByTestId("provenance-public-id")).toContainText(
      "impact_evidence/KEN-042"
    );
    await expect(page.getByTestId("provenance-root-hash")).not.toBeEmpty();
  });

  test("labels itself FIXTURE when the backend is absent", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });

    // The assertion that carries the weight: a 200-less, unreachable backend
    // must never be presented as a live read.
    await expect(page.getByTestId("provenance-source")).toContainText("Fixture");
    await expect(page.getByTestId("provenance-panel")).toHaveAttribute(
      "data-source",
      "fixture"
    );
  });

  test("explains WHY it degraded, in a live region", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });

    const reason = page.getByTestId("provenance-reason");
    await expect(reason).toBeVisible();
    // A screen-reader user must hear the degradation too, not just see it.
    await expect(reason).toHaveAttribute("role", "status");
    await expect(reason).toContainText(/no cloudinary call was made/i);
  });

  test("renders the transformation chain as an ordered list", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });

    const chain = page.getByTestId("provenance-chain");
    await expect(chain.locator("li")).toHaveCount(3);
    // Order is the whole point of a chain: an unordered set of transformations
    // does not tell you what was done, only what exists.
    await expect(chain).toHaveJSProperty("tagName", "OL");
  });

  test("states the C2PA status in words, not colour alone", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });

    const c2pa = page.getByTestId("provenance-c2pa");
    // Greyscale-printable: a word is present regardless of how it is rendered.
    await expect(c2pa).toContainText("Content verified");
    await expect(c2pa).toContainText("✔");
  });

  test("is reachable and labelled for assistive tech", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });

    const panel = page.getByTestId("provenance-panel");
    await expect(panel).toHaveAttribute("aria-labelledby", "provenance-heading");
    await expect(page.locator("#provenance-heading")).toHaveText("Provenance");
  });

  test("survives a slow backend by degrading rather than hanging", async ({ page }) => {
    // A stage demo on bad wifi must produce a panel, not a spinner. The client's
    // timeout is 4s, so allow generous headroom for CI and still require the
    // fixture to have appeared.
    await page.route("**/api/v1/assets/**", async (route) => {
      await new Promise((r) => setTimeout(r, 8000));
      await route.abort();
    });

    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("provenance-source")).toContainText("Fixture", {
      timeout: 15_000,
    });
  });

  test("does not claim Live when the response is fixture-mode", async ({ page }) => {
    // The subtle one. A 200 response whose `_provenance.mode` is `fixture` means
    // the backend served LOCAL data. Trusting the status code would badge that
    // as Live, which is the same class of error as the backend's own harness
    // reporting PASS on a call that did nothing.
    await page.route("**/api/v1/assets/**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          public_id: "impact_evidence/KEN-042/raw_capture_month18",
          master: {
            public_id: "impact_evidence/KEN-042/raw_capture_month18",
            folder: "impact_evidence/KEN-042",
            asset_type: "image",
          },
          content_hash: { algorithm: "SHA-256", root_hash: "a".repeat(64) },
          c2pa_provenance: "C2PA_VERIFIED",
          transformations: [],
          transformation_log_live: false,
          note: "local fixtures",
          _provenance: {
            request_id: "abc123",
            generated_at: "2026-09-28T00:00:00Z",
            mode: "fixture",
            evidence: "FIXTURE — synthetic, no Cloudinary call was made",
            app_env: "development",
            elapsed_ms: 0.4,
            path: "/api/v1/assets/x/provenance",
            method: "GET",
            provenance_endpoint: "http://localhost:8000/api/v1/assets/{id}/provenance",
            caveat: "Figures in this response are fixtures.",
          },
        }),
      })
    );

    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("provenance-source")).toContainText("Fixture");
  });

  test("badges Live only when the backend says it is live", async ({ page }) => {
    await page.route("**/api/v1/assets/**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          public_id: "impact_evidence/KEN-042/raw_capture_month18",
          master: {
            public_id: "impact_evidence/KEN-042/raw_capture_month18",
            folder: "impact_evidence/KEN-042",
            asset_type: "image",
          },
          content_hash: { algorithm: "SHA-256", root_hash: "b".repeat(64) },
          c2pa_provenance: "C2PA_MUTATED",
          transformations: [{ transformation: "e_sharpen:60" }],
          transformation_log_live: true,
          note: "Transformation chain read from the Cloudinary API.",
          _provenance: {
            request_id: "def456",
            generated_at: "2026-09-28T00:00:00Z",
            mode: "live",
            evidence: "live Cloudinary",
            app_env: "production",
            elapsed_ms: 12.1,
            path: "/api/v1/assets/x/provenance",
            method: "GET",
            provenance_endpoint: "https://veritas.example/api/v1/assets/{id}/provenance",
            caveat: "",
          },
        }),
      })
    );

    await page.goto("/", { waitUntil: "domcontentloaded" });

    await expect(page.getByTestId("provenance-source")).toContainText("Live");
    // No degradation banner when genuinely live.
    await expect(page.getByTestId("provenance-reason")).toHaveCount(0);
    // And an altered asset is not presented as verified.
    await expect(page.getByTestId("provenance-c2pa")).toContainText(
      "Content altered"
    );
  });
});
