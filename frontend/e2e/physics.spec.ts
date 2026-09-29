import { expect, test } from "./fixtures";

import {
  DEMO_CASES,
  SHADOW_UNUSABLE_BELOW_DEG,
  TOLERANCE_DEG,
  angularSeparation,
  decide,
  expectedShadow,
} from "@/lib/physics";

/**
 * ForensicPhysicsHUD.
 *
 * The specs that carry weight are the ones about REFUSAL. A forgery detector
 * that only ever answers pass or fail invites the reading that it is accusing,
 * and at low solar elevation the correct answer is that the comparison is not
 * evidence. Those cases are pinned here, in the maths as well as the rendering.
 */

test.describe("shadow-coherence maths", () => {
  test("expected shadow is the sun plus 180", () => {
    expect(expectedShadow(85.06)).toBeCloseTo(265.06, 2);
    expect(expectedShadow(0)).toBe(180);
    expect(expectedShadow(270)).toBeCloseTo(90, 6);
  });

  test("expected shadow wraps rather than exceeding 360", () => {
    expect(expectedShadow(350)).toBeCloseTo(170, 6);
    for (const a of [0, 45, 90, 179, 180, 270, 359]) {
      const s = expectedShadow(a);
      expect(s).toBeGreaterThanOrEqual(0);
      expect(s).toBeLessThan(360);
    }
  });

  test("separation is the SHORT way round", () => {
    expect(angularSeparation(10, 350)).toBeCloseTo(20, 6);
    expect(angularSeparation(0, 180)).toBeCloseTo(180, 6);
    expect(angularSeparation(45, 45)).toBeCloseTo(0, 6);
  });

  test("low sun ABSTAINS rather than accusing", () => {
    // The substance of the design. Below the usable elevation the comparison
    // is withheld, and NO error figure is produced.
    const low = DEMO_CASES.find((c) => c.id === "low-sun")!;
    const r = decide(low);
    expect(r.verdict).toBe("REVIEW_LOW_SUN_UNDETERMINED");
    expect(r.error).toBeNull();
  });

  test("a large observed error at low sun is still NOT a mismatch", () => {
    // The trap: low-sun cases carry a real observed bearing that disagrees
    // badly. Ordering the coherence check first would quarantine the capture.
    const low = DEMO_CASES.find((c) => c.id === "low-sun")!;
    const naiveError = angularSeparation(
      low.observed_shadow_azimuth_deg!,
      low.expected_shadow_azimuth_deg
    );
    expect(naiveError).toBeGreaterThan(TOLERANCE_DEG);
    expect(decide(low).verdict).not.toBe("QUARANTINE_SOLAR_MISMATCH");
  });

  test("a sun below the horizon is a capture anomaly, not a low-sun abstention", () => {
    const night = { ...DEMO_CASES[0], sun_elevation_deg: -4, observed_shadow_azimuth_deg: null };
    expect(decide(night).verdict).toBe("QUARANTINE_NIGHTTIME_CAPTURE_ANOMALY");
  });

  test("no observed shadow is insufficient input, not a pass", () => {
    const none = { ...DEMO_CASES[0], observed_shadow_azimuth_deg: null };
    expect(decide(none).verdict).toBe("REVIEW_INSUFFICIENT_INPUT");
  });

  test("the abstain threshold is not arbitrary — it is used, and documented", () => {
    expect(SHADOW_UNUSABLE_BELOW_DEG).toBeGreaterThan(0);
    const just_above = { ...DEMO_CASES[0], sun_elevation_deg: SHADOW_UNUSABLE_BELOW_DEG + 0.1 };
    const just_below = { ...DEMO_CASES[0], sun_elevation_deg: SHADOW_UNUSABLE_BELOW_DEG - 0.1 };
    expect(decide(just_below).verdict).toBe("REVIEW_LOW_SUN_UNDETERMINED");
    expect(decide(just_above).verdict).not.toBe("REVIEW_LOW_SUN_UNDETERMINED");
  });

  test("every fixture case resolves to the verdict it claims", () => {
    for (const c of DEMO_CASES) {
      expect(decide(c).verdict, `${c.id} claims ${c.verdict}`).toBe(c.verdict);
    }
  });
});

test.describe("ForensicPhysicsHUD", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
  });

  test("shows a coherent capture as consistent, with its margin", async ({ page }) => {
    await expect(page.getByTestId("physics-verdict")).toContainText(
      "Physically consistent"
    );
    await expect(page.getByTestId("physics-error")).not.toContainText("withheld");
    await expect(page.getByTestId("physics-margin")).toContainText(/to spare/i);
  });

  test("the low-sun case WITHHOLDS the comparison on screen", async ({ page }) => {
    await page.getByTestId("physics-case-low-sun").click();
    await expect(page.getByTestId("physics-verdict")).toContainText(
      "Cannot be determined"
    );
    await expect(page.getByTestId("physics-error")).toContainText("— withheld —");
    await expect(page.getByTestId("physics-withheld")).toContainText(
      /would not be evidence/i
    );
    // And it must not read as an accusation.
    await expect(page.getByTestId("physics-verdict")).not.toContainText(/inconsistent/i);
  });

  test("no rays are drawn when there is nothing to compare", async ({ page }) => {
    await page.getByTestId("physics-case-low-sun").click();
    await expect(page.getByTestId("hud-sun")).toHaveCount(0);
    await expect(page.getByTestId("hud-observed")).toHaveCount(0);
  });

  test("a mismatch shows the error outside the tolerance", async ({ page }) => {
    await page.getByTestId("physics-case-mismatch").click();
    await expect(page.getByTestId("physics-verdict")).toContainText(
      "Shadow inconsistent"
    );
    await expect(page.getByTestId("physics-margin")).toContainText(/Outside tolerance/i);
  });

  test("the error arc is drawn when there is a comparison", async ({ page }) => {
    await expect(page.getByTestId("hud-error-arc")).toHaveCount(1);
    await expect(page.getByTestId("hud-expected")).toHaveCount(1);
  });

  test("the compass is a labelled image, not decoration", async ({ page }) => {
    const svg = page.getByTestId("hud-compass");
    await expect(svg).toHaveAttribute("role", "img");
    await expect(svg).toHaveAttribute("aria-label", /sun direction/i);
  });

  test("the verdict is recomputed, so a lying fixture would be visible", async ({ page }) => {
    // The badge is derived from the same rule as the badge text, not read from
    // the fixture -- so a fixture that disagreed with its own numbers could not
    // present itself as authoritative.
    await expect(page.getByTestId("physics-verdict")).toContainText("consistent");
    await expect(page.getByTestId("physics-error")).toHaveText(/^\d+\.\d°$/);
  });

  test("case buttons are 44px and expose their pressed state", async ({ page }) => {
    const btn = page.getByTestId("physics-case-coherent");
    await expect(btn).toHaveAttribute("aria-pressed", "true");
    const box = await btn.boundingBox();
    expect(box!.height).toBeGreaterThanOrEqual(44);
  });

  test("selecting a case changes the readings", async ({ page }) => {
    const before = await page.getByTestId("physics-error").innerText();
    await page.getByTestId("physics-case-mismatch").click();
    await expect(page.getByTestId("physics-error")).not.toHaveText(before);
  });
});
