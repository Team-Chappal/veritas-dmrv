import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration.
 *
 * Two things are deliberate and worth not "fixing" later:
 *
 * 1. `webServer` starts Next in PRODUCTION mode (`next start` after `next
 *    build`) rather than `next dev`. The dev server compiles routes on demand
 *    and injects dev-only warnings, so a test run against it proves less than the
 *    artefact that actually ships. The cost is that `build` must run first, which
 *    is why the Makefile's `e2e` target depends on `build`.
 *
 * 2. No `testDir` pointing at a live backend by default. S6's exit criterion is
 *    that the demo works with the backend ENTIRELY ABSENT, so the suite is
 *    written to run without one. Tests that need API data use route mocking, not
 *    a running server, so they cannot silently depend on one being up.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["github"], ["list"]] : [["list"]],

  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    command: "npm run build && npm run start -- --port 3100",
    url: "http://127.0.0.1:3100",
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});
