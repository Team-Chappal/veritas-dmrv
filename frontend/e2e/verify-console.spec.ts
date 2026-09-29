import { expect, test } from "@playwright/test";

/**
 * The verification console — the thing a judge actually operates.
 *
 * These specs are about BEHAVIOUR a person can see, not about a component
 * existing. The gap that produced this console was that every capability was
 * present and none was reachable: a search box, three preset buttons, filter
 * chips, and no indication of which of those a judge was meant to press. So the
 * specs here type into fields and read the output, because that is the
 * interaction the pitch depends on.
 *
 * The three outcomes are all first-class. A tool that only ever says yes or no
 * invites the reading that it is accusing, and "cannot be determined" is the
 * most valuable thing this console can say.
 */

test.describe("verification console", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("verify-console")).toBeVisible();
  });

  test("a judge can type a claim and read a verdict", async ({ page }) => {
    await page.getByTestId("input-latitude").fill("-1.292");
    await page.getByTestId("input-longitude").fill("36.822");
    await page.getByTestId("input-time").fill("2026-09-22T08:15:30");
    await page.getByTestId("input-observed").fill("258.1");
    await page.getByTestId("verify-submit").click();

    await expect(page.getByTestId("verdict")).toContainText("Consistent with the claim");
    // The numbers a judge would check by hand.
    await expect(page.getByTestId("out-azimuth")).toHaveText("85.06°");
    await expect(page.getByTestId("out-expected")).toHaveText("265.06°");
    await expect(page.getByTestId("out-error")).toHaveText("6.96°");
  });

  test("a doctored timestamp is caught", async ({ page }) => {
    await page.getByTestId("preset-fraud").click();
    await expect(page.getByTestId("verdict")).toContainText("Contradicted by the light");
    // The reason must SAY how far off, not just that it failed.
    const reason = await page.getByTestId("verdict-reason").innerText();
    expect(reason).toMatch(/outside the 12° tolerance/);
    expect(reason).toMatch(/quarantin|disqualif/i);
  });

  test("a low sun WITHHOLDS the comparison rather than accusing", async ({ page }) => {
    await page.getByTestId("preset-abstain").click();
    await expect(page.getByTestId("verdict")).toContainText("Cannot be determined");
    // No error figure, because there is no error to show.
    await expect(page.getByTestId("out-error")).toHaveText("— withheld —");
    // And it must not read as an accusation. Scoped to the verdict and its
    // reason: the output block also carries the standing disclaimer, which uses
    // the word "contradicted" to explain what each result means, so searching the
    // whole block failed on the footnote.
    const verdict = await page.getByTestId("verdict").innerText();
    const reason = await page.getByTestId("verdict-reason").innerText();
    for (const text of [verdict, reason]) {
      expect(text).not.toMatch(/contradicted/i);
      expect(text).not.toMatch(/fraud|tamper|spoof|doctored/i);
    }
  });

  test("a sun below the horizon is impossible, not merely inconsistent", async ({ page }) => {
    await page.getByTestId("input-time").fill("2026-09-22T23:00:00");
    await page.getByTestId("verify-submit").click();
    await expect(page.getByTestId("verdict")).toContainText("Impossible at that time");
    // A sunlit photo cannot have a shadow when the sun is down.
    await expect(page.getByTestId("out-azimuth")).toHaveText("—");
  });

  test("every preset produces a result, so no button is decorative", async ({ page }) => {
    for (const id of ["genuine", "fraud", "abstain"]) {
      await page.getByTestId(`preset-${id}`).click();
      await expect(page.getByTestId("console-output")).toBeVisible();
      await expect(page.getByTestId("verdict-reason")).not.toBeEmpty();
    }
  });

  test("the audit receipt is available and states the limit of the check", async ({ page }) => {
    await page.getByTestId("preset-genuine").click();
    await page.getByTestId("console-output").locator("summary").click();
    const receipt = await page.getByTestId("receipt").innerText();
    expect(receipt).toContain("veritas.dmrv/verification");
    expect(receipt).toContain("verdict   PHYSICS_PASS");
    // The honest line has to be IN the receipt, not only in the prose.
    expect(receipt).toMatch(/not proof of authenticity/i);
    expect(receipt).toMatch(/pvlib/);
  });

  test("it works with NO backend — the deployed demo has none", async ({ page }) => {
    // The public URL is the one a judge opens, and it has no server. If this
    // console needed one, the whole point of it would be unreachable.
    const attempted: string[] = [];
    page.on("request", (r) => {
      if (r.url().includes("/api/")) attempted.push(r.url());
    });
    await page.getByTestId("preset-fraud").click();
    await expect(page.getByTestId("verdict")).toBeVisible();
    expect(attempted, `the console called the API: ${attempted.join(", ")}`).toEqual([]);
  });

  test("nonsense input is refused with a usable message, not a NaN verdict", async ({ page }) => {
    await page.getByTestId("input-latitude").fill("91");
    await page.getByTestId("verify-submit").click();
    await expect(page.getByTestId("console-error")).toContainText("between -90 and 90");
    // And no verdict was produced from a bad input.
    await expect(page.getByTestId("console-output")).toHaveCount(0);
  });

  test("a blank shadow bearing asks for the input instead of guessing", async ({ page }) => {
    await page.getByTestId("input-observed").fill("");
    await page.getByTestId("verify-submit").click();
    await expect(page.getByTestId("verdict-reason")).toContainText("No shadow bearing was supplied");
    await expect(page.getByTestId("out-observed")).toHaveText("not supplied");
  });

  test("the controls meet the 44px minimum", async ({ page }) => {
    for (const id of ["verify-submit", "preset-genuine", "input-latitude"]) {
      const box = await page.getByTestId(id).boundingBox();
      expect(box!.height, `${id} is ${box!.height}px tall`).toBeGreaterThanOrEqual(44);
    }
  });

  test("the form is usable from the keyboard alone", async ({ page }) => {
    // The fields are PRE-FILLED with a working example, which is the right
    // default for a judge. It also means typing without clearing appends to the
    // existing value and produces something unparseable -- which is what the
    // first version of this spec did, and why it failed on a correct form.
    const typeOver = async (testId: string, value: string) => {
      await page.getByTestId(testId).focus();
      await page.keyboard.press("ControlOrMeta+A");
      await page.keyboard.press("Delete");
      await page.keyboard.type(value);
    };

    await typeOver("input-latitude", "-1.292");
    await page.keyboard.press("Tab");
    await typeOver("input-longitude", "36.822");
    await page.keyboard.press("Tab");
    await typeOver("input-time", "2026-09-22T08:15:30");
    await page.keyboard.press("Tab");
    await typeOver("input-observed", "258.1");
    // Assert where focus actually is, rather than assuming the tab order -- the
    // first version pressed Enter after one Tab and submitted a form the judge
    // could not see their way through.
    await page.keyboard.press("Tab");
    await expect(page.getByTestId("verify-submit")).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("verdict")).toContainText("Consistent with the claim");
  });

  test("the inputs are labelled, not placeholders", async ({ page }) => {
    // A placeholder disappears the moment you type, which leaves a judge with a
    // field they cannot identify on a form they did not read.
    for (const id of ["input-latitude", "input-longitude", "input-time"]) {
      const label = page.locator(`label:has([data-testid="${id}"])`);
      await expect(label).toHaveCount(1);
      await expect(label).toContainText(/.+/);
    }
  });
});
