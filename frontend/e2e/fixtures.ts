/**
 * The base `test`, with the runtime API URL set for every spec that uses it.
 *
 * WHY THIS EXISTS — it is a coupling that hid for a long time
 * ---------------------------------------------------------
 * The e2e build is built WITHOUT `NEXT_PUBLIC_API_URL`, because the S6 exit
 * criterion is that the app works with the backend entirely absent, and that is
 * also the artefact a judge-facing deploy gets.
 *
 * The live-path specs mock the API by intercepting requests. For years they got
 * an interceptable URL from a `?? "http://localhost:8000"` default inside the
 * client — a lie that happened to be true on a developer machine and produced a
 * dead request on a deployed one. When that default was correctly removed, four
 * specs failed and the live path lost its coverage entirely.
 *
 * Both facts were only discoverable together, and neither was visible in the
 * test that covered the default. The fix is a documented RUNTIME override
 * (`window.__VERITAS_API_URL__`, which an operator can also use to re-point a
 * deployed build without a rebuild) rather than a reinstated lie.
 *
 * `demo-build.spec.ts` imports from `@playwright/test` directly and therefore
 * opts out, which is what keeps the no-API state covered.
 */
import { test as base, expect } from "@playwright/test";

/**
 * The URL the mocked API is intercepted at. localhost, because Playwright
 * intercepts before the request leaves the process -- nothing binds the port.
 */
export const RUNTIME_API_URL = "http://localhost:8000";

export const test = base.extend<{ runtimeApi: string }>({
  // An auto fixture: it runs for every test that uses this `test`, with no
  // opt-in call in the spec body, so a new spec cannot forget it.
  runtimeApi: [
    async ({ page }, use) => {
      await page.addInitScript((url) => {
        (window as unknown as { __VERITAS_API_URL__?: string }).__VERITAS_API_URL__ = url;
      }, RUNTIME_API_URL);
      await use(RUNTIME_API_URL);
    },
    { auto: true },
  ],
});

export { expect };
