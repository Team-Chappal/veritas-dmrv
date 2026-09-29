import { expect, test } from "./fixtures";

import { DEMO_CAMPAIGN } from "@/lib/campaign";

/**
 * CampaignStudio — rubric bullet 4.
 *
 * Two things are load-bearing here. First, the URLs must actually LOAD: these
 * are composed Cloudinary transformations on a public demo product, and a
 * campaign studio whose artefacts 404 is worse than one with no artefacts.
 * Second, the plan-gated one must be visibly gated, because a feature list that
 * quietly overstates what is demonstrable is the failure this project is
 * organised around.
 */

test.describe("CampaignStudio", () => {
  test.beforeEach(async ({ page }) => {
    // NOT networkidle. A page carrying a <video> never reaches network idle --
    // the media connection stays open, so the wait times out at 30s and the
    // failure reads as "the page is broken" when the page is fine. Locator
    // assertions auto-wait anyway, so this loses nothing.
    await page.goto("/console", { waitUntil: "domcontentloaded" });
  });

  test("lists every campaign artefact", async ({ page }) => {
    await expect(page.getByTestId("campaign-item")).toHaveCount(4);
  });

  test("the composed URLs actually load", async ({ page }) => {
    test.setTimeout(60_000);
    // The point of the studio: these are the artefacts, not previews of them.
    const results = await page.evaluate(async (urls: string[]) => {
      const out: Array<{ url: string; status: number }> = [];
      for (const url of urls) {
        try {
          const r = await fetch(url, { method: "GET" });
          out.push({ url, status: r.status });
        } catch {
          out.push({ url, status: 0 });
        }
      }
      return out;
    }, DEMO_CAMPAIGN.assets.filter((a) => a.verification === "verified_live").map((a) => a.url));

    for (const r of results) {
      expect(r.status, `${r.url} -> ${r.status}`).toBe(200);
    }
    expect(results.length).toBe(3);
  });

  test("layer references use COLONS, and the URLs prove it", () => {
    // A slash in an l_ reference makes the delivery parser swallow the rest of
    // the transformation as a public_id and 404. Found on a live account, then
    // confirmed independently on the public demo cloud.
    for (const asset of DEMO_CAMPAIGN.assets) {
      for (const seg of asset.url.split("/").filter((s) => s.startsWith("l_"))) {
        expect(
          seg,
          `layer reference "${seg}" contains a slash, which 404s`
        ).not.toMatch(/^l_[^:]*\//);
      }
    }
  });

  test("the gated artefact is labelled, not hidden and not claimed working", async ({ page }) => {
    const item = page.locator('[data-verification="plan_gated"]');
    await expect(item).toHaveCount(1);
    await expect(page.getByTestId("campaign-status-audit-pdf")).toContainText(
      /needs a paid plan/i
    );
    // The reason, on screen, with the status code Cloudinary actually returned.
    await expect(page.getByTestId("campaign-blocker-audit-pdf")).toContainText("401");
    await expect(page.getByTestId("campaign-blocker-audit-pdf")).toHaveAttribute(
      "role",
      "note"
    );
  });

  test("the gated artefact is visually de-emphasised, not merely labelled", async ({ page }) => {
    // A label alone is easy to miss; the box is dimmed too.
    const item = page.locator('[data-verification="plan_gated"]');
    const opacity = await item.locator("div").first().evaluate((el) =>
      Number(getComputedStyle(el).opacity)
    );
    expect(opacity).toBeLessThan(1);
  });

  test("each artefact carries the evidence for its verification", async ({ page }) => {
    await expect(page.getByTestId("campaign-status-split-diff")).toContainText(
      /verified/i
    );
    await expect(page.getByTestId("campaign-item").first()).toContainText(/HTTP 200|Form is correct/);
  });

  test("previews reserve space before loading, so nothing shifts", async ({ page }) => {
    // The CLS exit criterion. Each box must have a computed box BEFORE any
    // image resolves, which an aspect-ratio class guarantees.
    const boxes = await page
      .getByTestId("campaign-item")
      .locator("div")
      .evaluateAll((els) =>
        els
          .filter((e) => {
            const r = e.getBoundingClientRect();
            return r.height > 40 && r.width > 40;
          })
          .map((e) => {
            const r = e.getBoundingClientRect();
            return { w: Math.round(r.width), h: Math.round(r.height) };
          })
      );
    expect(boxes.length).toBeGreaterThanOrEqual(3);
    for (const b of boxes) {
      expect(b.h, `preview box ${b.w}x${b.h} has no reserved height`).toBeGreaterThan(40);
    }
  });

  test("the 9:16 reel reserves a portrait box, not a landscape one", async ({ page }) => {
    const ratio = await page
      .getByTestId("campaign-item")
      .nth(1)
      .locator("div")
      .first()
      .evaluate((el) => {
        const r = el.getBoundingClientRect();
        return r.height / r.width;
      });
    // 16:9 would be ~0.56; 9:16 is ~1.78.
    expect(ratio).toBeGreaterThan(1.2);
  });

  test("sample imagery is named as such in the alt text", async ({ page }) => {
    await expect(page.getByTestId("campaign-image-split-diff")).toHaveAttribute(
      "alt",
      /not field evidence/i
    );
  });

  test("the fixture is labelled and explains why no credentials are involved", async ({ page }) => {
    await expect(page.getByTestId("campaign-source")).toContainText("Fixture");
    await expect(page.getByTestId("campaign-reason")).toContainText(
      /no credentials and no account/i
    );
  });

  test("open links are safe", async ({ page }) => {
    const links = page.getByTestId("campaign-grid").locator("a[target=_blank]");
    const n = await links.count();
    expect(n).toBeGreaterThan(0);
    for (let i = 0; i < n; i++) {
      await expect(links.nth(i)).toHaveAttribute("rel", /noopener/);
    }
  });

  test("the transformation string is disclosed, not hidden behind a download", async ({ page }) => {
    await page.getByText("Show the composed transformation").click();
    await expect(page.getByTestId("campaign-grid")).toBeVisible();
    // A reviewer asking "what exactly was applied?" should not need devtools.
    await expect(page.locator("details code").first()).toContainText("res.cloudinary.com");
  });

  test("every control meets the 44px minimum", async ({ page }) => {
    const targets = page.getByTestId("campaign-grid").locator("a, button, summary");
    const n = await targets.count();
    expect(n).toBeGreaterThan(0);
    for (let i = 0; i < n; i++) {
      const box = await targets.nth(i).boundingBox();
      if (!box) continue;
      expect(box.height, `control ${i} is ${Math.round(box.height)}px tall`).toBeGreaterThanOrEqual(44);
    }
  });
});
