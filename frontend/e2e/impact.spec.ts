import { expect, test } from "./fixtures";

/**
 * ProofOfImpactStudio — rubric bullet 3.
 *
 * The load-bearing assertions are the ones about QUALIFICATION: that a canopy
 * delta is never presented without the registration verdict that licenses it, and
 * that a marginal registration downgrades the delta in words. A component that
 * renders "+31.7%" prominently and the alignment quality quietly underneath has
 * inverted the whole point of the comparison.
 */

test.describe("ProofOfImpactStudio", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
  });

  test("shows the inlier ratio AND the canopy delta", async ({ page }) => {
    await expect(page.getByTestId("inlier-ratio")).toBeVisible();
    await expect(page.getByTestId("canopy-delta")).toBeVisible();
    await expect(page.getByTestId("inlier-ratio")).toHaveText(/^0\.\d{3}$/);
  });

  test("states the registration verdict in words, not a colour", async ({ page }) => {
    const v = page.getByTestId("inlier-verdict");
    await expect(v).toBeVisible();
    await expect(v).toContainText(/Registration/i);
    // The fixture sits just below target, so the branch that matters is the
    // "usable but below target" one, not an all-clear.
    await expect(v).toContainText(/below target/i);
  });

  test("explains what the ratio MEANS, not just what it is", async ({ page }) => {
    await expect(page.getByTestId("impact-studio")).toContainText(
      /canopy figures below can be attributed|read the canopy/i
    );
  });

  test("downgrades the delta in words when registration is marginal", async ({ page }) => {
    // The whole reason the verdict is on the page: a +31.7% figure with a
    // marginal alignment is a number about the alignment, not about trees.
    const caveat = page.getByTestId("delta-caveat");
    await expect(caveat).toBeVisible();
    await expect(caveat).toHaveAttribute("role", "note");
    await expect(caveat).toContainText(/Indicative only/i);
    await expect(caveat).toContainText(/not suitable for a compliance filing/i);
  });

  test("the registration verdict is rendered BEFORE the delta", async ({ page }) => {
    // Reading order is the design: a reviewer must meet the caveat first.
    const order = await page.evaluate(() => {
      const i = document.querySelector('[data-testid="inlier-ratio"]');
      const d = document.querySelector('[data-testid="canopy-delta"]');
      if (!i || !d) return null;
      return (
        i.compareDocumentPosition(d) & Node.DOCUMENT_POSITION_FOLLOWING ? "inlier-first" : "delta-first"
      );
    });
    expect(order).toBe("inlier-first");
  });

  test("the slider is a real slider control", async ({ page }) => {
    const handle = page.getByTestId("slider-handle");
    await expect(handle).toHaveAttribute("role", "slider");
    await expect(handle).toHaveAttribute("aria-valuemin", "0");
    await expect(handle).toHaveAttribute("aria-valuemax", "100");
    await expect(handle).toHaveAttribute("aria-valuetext", /Baseline/);
  });

  test("arrow keys move the comparison", async ({ page }) => {
    const handle = page.getByTestId("slider-handle");
    await handle.focus();
    const start = Number(await handle.getAttribute("aria-valuenow"));

    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("ArrowRight");
    const after = Number(await handle.getAttribute("aria-valuenow"));
    expect(after).toBeGreaterThan(start);

    await page.keyboard.press("ArrowLeft");
    expect(Number(await handle.getAttribute("aria-valuenow"))).toBe(after - 5);
  });

  test("Home and End jump to the extremes", async ({ page }) => {
    const handle = page.getByTestId("slider-handle");
    await handle.focus();

    await page.keyboard.press("End");
    expect(await handle.getAttribute("aria-valuenow")).toBe("100");
    await page.keyboard.press("Home");
    expect(await handle.getAttribute("aria-valuenow")).toBe("0");
  });

  test("the comparison position cannot leave its bounds", async ({ page }) => {
    const handle = page.getByTestId("slider-handle");
    await handle.focus();
    await page.keyboard.press("Home");
    for (let i = 0; i < 5; i++) await page.keyboard.press("ArrowLeft");
    expect(await handle.getAttribute("aria-valuenow")).toBe("0");

    await page.keyboard.press("End");
    for (let i = 0; i < 5; i++) await page.keyboard.press("ArrowRight");
    expect(await handle.getAttribute("aria-valuenow")).toBe("100");
  });

  test("Page keys move in coarser steps than arrows", async ({ page }) => {
    const handle = page.getByTestId("slider-handle");
    await handle.focus();
    await page.keyboard.press("Home");
    await page.keyboard.press("PageUp");
    const coarse = Number(await handle.getAttribute("aria-valuenow"));
    expect(coarse).toBe(10);
  });

  test("the handle is a 44px target", async ({ page }) => {
    const box = await page.getByTestId("slider-handle").boundingBox();
    expect(box!.height).toBeGreaterThanOrEqual(44);
    expect(box!.width).toBeGreaterThanOrEqual(44);
  });

  test("BOTH HALVES SHOW THE SAME FIELD OF VIEW", async ({ page }) => {
    // A before/after comparison whose halves are not the same scale is not a
    // comparison. The previous version pinned the progress image to the track's
    // clientWidth, falling back to 800px before the ref resolved -- so in a 602px
    // track the progress frame rendered at 800px against a baseline scaled to
    // 602. The edges lined up, which is why a screenshot review missed it.
    const panel = page.getByTestId("impact-studio");
    const track = await page.getByTestId("slider-track").boundingBox();
    // Scoped to THIS panel. `page.locator("img").first()` is document order, so
    // the CampaignStudio previews -- inserted earlier on the page -- captured it,
    // and the spec started measuring the wrong image. It failed only when the
    // whole suite ran, which is the worst way for a locator bug to surface.
    const img = await panel.locator("img").first().boundingBox();
    expect(track).not.toBeNull();
    expect(img).not.toBeNull();
    expect(
      Math.abs(track!.width - img!.width),
      `progress frame is ${Math.round(img!.width)}px in a ${Math.round(
        track!.width
      )}px track, so the halves show the same scene at different magnifications`
    ).toBeLessThanOrEqual(2);
  });

  test("the progress layer tracks the split position", async ({ page }) => {
    const handle = page.getByTestId("slider-handle");
    await handle.focus();
    await page.keyboard.press("Home");
    const layerAtZero = (await page.getByTestId("slider-progress-layer").boundingBox())!.width;
    const track = (await page.getByTestId("slider-track").boundingBox())!.width;
    // At Home the progress frame should be fully visible.
    expect(Math.abs(layerAtZero - track)).toBeLessThanOrEqual(2);
  });

  test("both frames are labelled for assistive tech", async ({ page }) => {
    // Scoped for the same reason as above.
    const imgs = page.getByTestId("impact-studio").locator("img");
    const n = await imgs.count();
    expect(n).toBeGreaterThan(0);
    for (let i = 0; i < n; i++) {
      const alt = await imgs.nth(i).getAttribute("alt");
      expect(alt && alt.trim().length, `image ${i} has no alt text`).toBeTruthy();
    }
  });

  test("the fixture scenes say they are synthetic in the ACCESSIBLE text", async ({ page }) => {
    // The label was painted into the SVG only, so it never reached a screen
    // reader -- the one user who cannot check the pixels. It has to be in the
    // alt text, not merely drawn.
    // Scoped, for the same reason: an unscoped `img.first()` captured the
    // CampaignStudio preview, whose alt says "not field evidence" but not
    // "synthetic" -- so this asserted against the wrong element.
    const img = page.getByTestId("impact-studio").locator("img").first();
    await expect(img).toHaveAttribute("alt", /synthetic/i);
    await expect(img).toHaveAttribute("alt", /not field evidence/i);
  });

  test("labels itself FIXTURE and says no registration was run", async ({ page }) => {
    await expect(page.getByTestId("impact-source")).toContainText("Fixture");
    await expect(page.getByTestId("impact-reason")).toContainText(
      /no sift registration was run/i
    );
  });
});
