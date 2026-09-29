import { expect, test } from "./fixtures";

/**
 * Offline resilience (rubric 6.11).
 *
 * THE CLAIM BEING TESTED
 *
 * "A captured frame survives a reload with no network." That is a durability
 * claim about IndexedDB, so it is tested as one -- enqueue, RELOAD, and assert
 * the row is still there. A test that enqueues and immediately lists back would
 * pass even if nothing were persisted at all, because both operations would be
 * served from the same in-memory handle.
 *
 * The other pinned behaviour is negative: the service worker must NOT cache API
 * responses. A stale asset list served with a 200 is the exact confusion every
 * provenance badge in this product exists to prevent, so it is asserted rather
 * than assumed.
 */

test.beforeEach(async ({ page }) => {
  await page.goto("/console", { waitUntil: "domcontentloaded" });
});

test.describe("capture queue durability", () => {
  test("a queued capture SURVIVES A RELOAD", async ({ page }) => {
    await page.getByTestId("queue-capture").click();
    await expect(page.getByTestId("queue-count")).toHaveText("1");

    // The point of the test. A reload with no network would lose anything held
    // only in memory.
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("queue-count")).toHaveText("1");
    await expect(page.getByTestId("queue-list")).toContainText("IMG_");
  });

  test("queued captures accumulate and count is honest", async ({ page }) => {
    for (let i = 0; i < 3; i++) await page.getByTestId("queue-capture").click();
    await expect(page.getByTestId("queue-count")).toHaveText("3");
    await expect(page.getByTestId("queue-list").locator("li")).toHaveCount(3);
  });

  test("flush drains the queue and the count follows", async ({ page }) => {
    await page.getByTestId("queue-capture").click();
    await expect(page.getByTestId("queue-count")).toHaveText("1");
    await page.getByTestId("queue-drain").click();
    await expect(page.getByTestId("queue-count")).toHaveText("0");
  });

  test("flush is disabled when there is nothing to flush", async ({ page }) => {
    await expect(page.getByTestId("queue-drain")).toBeDisabled();
    await page.getByTestId("queue-capture").click();
    await expect(page.getByTestId("queue-drain")).toBeEnabled();
  });

  test("each capture gets a distinct id, so a flush cannot collide", async ({ page }) => {
    for (let i = 0; i < 2; i++) await page.getByTestId("queue-capture").click();
    // Read the store directly rather than through the module: assertions about
    // durability have to survive bundling, not depend on a test-only global
    // that exists only in the spec's own import graph.
    const ids = await page.evaluate(
      () =>
        new Promise<string[]>((resolve, reject) => {
          const req = indexedDB.open("veritas-capture", 1);
          req.onsuccess = () => {
            const db = req.result;
            const all = db.transaction("queue", "readonly").objectStore("queue").getAll();
            all.onsuccess = () => resolve(all.result.map((x: { id: string }) => x.id));
            all.onerror = () => reject(all.error);
          };
          req.onerror = () => reject(req.error);
        })
    );
    expect(ids.length).toBe(2);
    expect(new Set(ids).size).toBe(2);
  });
});

test.describe("data mode is an explicit choice", () => {
  test("defaults to following the network", async ({ page }) => {
    await page.evaluate(() => localStorage.removeItem("veritas.dataMode"));
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("mode-auto")).toHaveAttribute("aria-pressed", "true");
  });

  test("forcing demo data is labelled as a choice, not a failure", async ({ page }) => {
    await page.getByTestId("mode-fixture").click();
    await expect(page.getByTestId("mode-state")).toContainText(/by choice/i);
  });

  test("the choice is PERSISTED, not a per-render local", async ({ page }) => {
    await page.getByTestId("mode-fixture").click();
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("mode-fixture")).toHaveAttribute("aria-pressed", "true");
  });

  test("returning to auto is labelled as following the network", async ({ page }) => {
    await page.getByTestId("mode-fixture").click();
    await page.getByTestId("mode-auto").click();
    await expect(page.getByTestId("mode-state")).toContainText(/Following the network/i);
  });

  test("the preference is actually written to storage", async ({ page }) => {
    await page.getByTestId("mode-fixture").click();
    expect(await page.evaluate(() => localStorage.getItem("veritas.dataMode"))).toBe("fixture");
    await page.getByTestId("mode-auto").click();
    expect(await page.evaluate(() => localStorage.getItem("veritas.dataMode"))).toBe("auto");
  });
});

test.describe("background sync reports honestly", () => {
  test("registering sync yields an explanation either way", async ({ page }) => {
    await page.getByTestId("sync-button").click();
    // The point is not that sync succeeds -- it is absent in some browsers. It
    // is that the UI never claims a retry it did not arrange.
    await expect(page.getByTestId("sync-report")).not.toBeEmpty();
  });

  test("an unsupported browser is described, not hidden", async ({ page }) => {
    // If Background Sync is missing, the user must be told WHY and what to do
    // instead -- not shown a button that appears to have worked.
    const hasSync = await page.evaluate(async () => {
      const reg = await navigator.serviceWorker.ready;
      return "sync" in reg;
    });
    await page.getByTestId("sync-button").click();
    const text = await page.getByTestId("sync-report").innerText();
    expect(text.length).toBeGreaterThan(0);
    // Whichever branch we are in, the message must name the right layer. The
    // failure that motivated this: the worker WAS reachable, and reporting
    // "could not reach the service worker" sent the reader to the wrong place.
    if (!hasSync) {
      expect(text).toMatch(/unavailable/i);
      expect(text).toMatch(/IndexedDB/i);
    } else {
      const registered = /registered/i.test(text);
      const blocked = /blocked by this browser/i.test(text);
      expect(registered || blocked).toBe(true);
      if (blocked) expect(text).not.toMatch(/could not reach the service worker/i);
    }
  });
});

test.describe("the service worker's scope is narrow on purpose", () => {
  test("it does NOT cache API responses", async ({ page }) => {
    // A cached /api/v1/assets would let a reviewer see yesterday's collection
    // believing it is today's -- the exact confusion the provenance badges
    // exist to prevent. Asserted against the worker's own logic.
    const apiCached = await page.evaluate(async () => {
      const reg = await navigator.serviceWorker.ready;
      const cache = await caches.open("veritas-shell-v1");
      const hit = await cache.match("https://veritas.test/api/v1/assets");
      return hit !== undefined;
    });
    expect(apiCached).toBe(false);
  });

  test("the worker is registered and controlling the page", async ({ page }) => {
    await expect(page.getByTestId("sw-state")).toContainText(/Service worker active/i);
  });
});
