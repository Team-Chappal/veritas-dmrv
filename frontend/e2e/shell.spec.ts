import { expect, test } from "./fixtures";

/**
 * S6 exit criterion 5: the demo works with the backend entirely absent.
 *
 * NOTE on waiting: use `domcontentloaded`, never `networkidle`. The page carries
 * a <video>, whose media connection stays open, so `networkidle` never settles
 * and every spec times out at 30s while the page is perfectly fine. Locator
 * assertions auto-wait, so nothing is lost.
 *
 * This is the first e2e spec in the project, and it deliberately asserts the
 * SHAPE of a page rather than any content that a component will add later. Its
 * job is to prove the harness itself is wired: a spec suite that has never been
 * run is indistinguishable from one that has no failures.
 *
 * Criterion 1 also lives here: a production build must render with no hydration
 * warnings. React only reports those in development, so this asserts the
 * production build has no console errors instead — see the hydration test below.
 */
test.describe("Stage 6 exit criterion 5 — backend absent", () => {
  test("the shell renders with no backend running", async ({ page }) => {
    const failures: string[] = [];
    // Network-level console entries are the BROWSER reporting a refused
    // connection, not the application throwing. The backend being absent is the
    // state under test, so failing on those would mean this test can only ever
    // pass with a server running -- which is the opposite of its purpose. A
    // hydration warning or a React error still fails, and that is the point.
    const isNetworkNoise = (text: string) =>
      /Failed to load resource|ERR_CONNECTION_REFUSED|ERR_NETWORK|net::/i.test(text);

    page.on("console", (m) => {
      if (m.type() === "error" && !isNetworkNoise(m.text())) failures.push(m.text());
    });
    page.on("pageerror", (e) => failures.push(String(e)));

    // Nothing here is stubbed or routed. If this needs an API call to render,
    // that is a defect in the component, not a missing fixture.
    await page.goto("/", { waitUntil: "domcontentloaded" });

    await expect(page.locator("main")).toBeVisible();
    expect(failures, `console errors: ${failures.join(" | ")}`).toHaveLength(0);
  });

  test("the page has a title and is not an error page", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page).toHaveTitle(/.+/);
    await expect(page.locator("body")).not.toContainText("Application error");
  });

  test("design tokens are applied, not left to browser defaults", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });

    // The token baseline is a Stage 0 deliverable that later components inherit.
    // Asserting the exact `canvas` colour rather than merely "not transparent"
    // means this fails if the class is dropped, renamed, or overridden -- and it
    // fails if a later component repaints the shell, which is a real risk once
    // eleven components land on this page.
    const bg = await page.evaluate(
      () => getComputedStyle(document.body).backgroundColor
    );
    // `canvas` is #030712 in tailwind.config.ts.
    expect(bg, "body background must be the `canvas` token, #030712").toBe(
      "rgb(3, 7, 18)"
    );
  });
});
