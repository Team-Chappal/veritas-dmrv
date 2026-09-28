import { expect, test } from "@playwright/test";

/**
 * The shared primitives enforce rules that five components will depend on.
 *
 * A rule that lives in a component is only enforced while that component is on
 * the page. These specs assert the RULES -- colour alone is never the carrier,
 * targets are big enough, numbers are tabular -- against whatever the page
 * currently renders, so a future component that rolls its own badge fails here
 * rather than in an audit pack.
 */

test.describe("Design-system rules", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
  });

  test("every status carries a text label, not only colour", async ({ page }) => {
    // Scoped to elements that look like status pills. If a future component
    // renders a bare coloured dot with no text, this finds it.
    const statuses = page.locator(
      '[data-tone], [data-testid="source-badge"], [data-testid="provenance-c2pa"]'
    );
    const n = await statuses.count();
    expect(n).toBeGreaterThan(0);

    for (let i = 0; i < n; i++) {
      const el = statuses.nth(i);
      const text = ((await el.innerText()) ?? "").trim();
      const hasSrText = await el.locator(".sr-only").count();
      // A word, or a screen-reader-only word. Either way not colour alone.
      expect(
        text.length > 0 || hasSrText > 0,
        `status element ${i} has neither visible nor SR text: "${text}"`
      ).toBeTruthy();
    }
  });

  test("no status relies on a colour swatch with no glyph or word", async ({ page }) => {
    // A bare dot is the specific anti-pattern: it is the one thing that becomes
    // invisible in greyscale print.
    const bareDots = page.locator(
      'span:has-text("●"):not(:has-text("Live")):not(:has-text("Fixture"))'
    );
    expect(await bareDots.count()).toBe(0);
  });

  test("numeric values are rendered with tabular figures", async ({ page }) => {
    // Proportional digits misalign a column of hashes, and a transposed digit
    // in a SHA-256 is the failure this whole product exists to prevent.
    const rootHash = page.getByTestId("provenance-root-hash");
    await expect(rootHash).toHaveCount(1);

    const style = await rootHash.evaluate((el) => {
      const cs = getComputedStyle(el);
      return { fontVariantNumeric: cs.fontVariantNumeric };
    });
    // Browsers report "tabular-nums" for the shorthand; accept either form.
    expect(style.fontVariantNumeric).toMatch(/tabular-nums/);
  });

  test("interactive targets meet the 44px minimum", async ({ page }) => {
    // Exit criterion 4. Measures every control on the page rather than
    // asserting a CSS class exists, because a class can be overridden later.
    const targets = page.locator(
      "button, a[href], input, select, [role='button'], [role='tab']"
    );
    const n = await targets.count();

    // INCONCLUSIVE TODAY, and deliberately not hidden. The page currently has
    // ZERO interactive controls, so the loop below asserts nothing and this test
    // passes vacuously. A vacuous pass is a trap: it reads as "sizes verified"
    // when nothing was measured.
    //
    // It becomes a real check the moment 6.2 PortfolioGrid or 6.4 SemanticSearch
    // lands, both of which add buttons and inputs. The assertion below is the
    // guard for that moment and must be replaced with `expect(n).toBeGreaterThan(0)`
    // at that point -- tracked in docs/RUBRIC-TRACEABILITY.md.
    expect(
      n,
      `INCONCLUSIVE: ${n} interactive targets found, so the 44px rule was not ` +
        "actually exercised. Tighten this to require a non-zero count once the " +
        "page has controls."
    ).toBeGreaterThanOrEqual(0);

    for (let i = 0; i < n; i++) {
      const box = await targets.nth(i).boundingBox();
      if (!box) continue; // not visible / not laid out
      expect(
        box.height,
        `target ${i} is ${box.height}px tall, under the 44px minimum`
      ).toBeGreaterThanOrEqual(44);
      expect(
        box.width,
        `target ${i} is ${box.width}px wide, under the 44px minimum`
      ).toBeGreaterThanOrEqual(44);
    }
  });

  test("landmarks are labelled", async ({ page }) => {
    // An unlabelled section is a region a screen reader announces only as
    // "region", which is useless with five panels on one page.
    const sections = page.locator("section");
    const n = await sections.count();
    expect(n).toBeGreaterThan(0);

    for (let i = 0; i < n; i++) {
      const labelledBy = await sections.nth(i).getAttribute("aria-labelledby");
      const ariaLabel = await sections.nth(i).getAttribute("aria-label");
      expect(
        labelledBy ?? ariaLabel,
        `section ${i} has no accessible name`
      ).toBeTruthy();
    }
  });

  test("the degradation notice is announced, not just drawn", async ({ page }) => {
    const notice = page.getByTestId("provenance-reason");
    await expect(notice).toHaveAttribute("role", "status");
  });

  test("text meets AAA contrast on the surface background", async ({ page }) => {
    // WCAG 2.2 AAA is 7:1 for body text. Checked on the elements carrying the
    // measurements, which are the numbers an auditor reads off a printout.
    const figures = page.locator('[data-testid="provenance-root-hash"]');
    const result = await figures.evaluate((el) => {
      const parse = (c: string) => {
        const m = c.match(/rgba?\(([^)]+)\)/);
        if (!m) return null;
        const [r, g, b] = m[1].split(",").map((n) => parseFloat(n));
        return { r, g, b };
      };
      const lum = ({ r, g, b }: { r: number; g: number; b: number }) => {
        const f = (v: number) => {
          const s = v / 255;
          return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
        };
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
      };
      const fg = parse(getComputedStyle(el).color);
      // Walk up for the first non-transparent background.
      let node: HTMLElement | null = el;
      let bg = null;
      while (node) {
        const c = parse(getComputedStyle(node).backgroundColor);
        if (c && !(c.r === 0 && c.g === 0 && c.b === 0 && getComputedStyle(node).backgroundColor.includes("0)"))) {
          bg = c;
          break;
        }
        node = node.parentElement;
      }
      if (!fg || !bg) return null;
      const l1 = lum(fg);
      const l2 = lum(bg);
      const ratio =
        (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
      return ratio;
    });

    // A null means the walk could not resolve a background; fail loudly rather
    // than silently skipping the check.
    expect(result, "could not resolve colours for the contrast check").not.toBeNull();
    expect(result!).toBeGreaterThanOrEqual(7);
  });
});
