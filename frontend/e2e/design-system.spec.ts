import { expect, test } from "./fixtures";

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
    await page.goto("/console", { waitUntil: "domcontentloaded" });
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
    //
    // SELECTED BY SHAPE, NOT BY SIBLING TEXT. The previous version was
    // `span:has-text("●"):not(:has-text("Live"))`, which asked whether a dot's
    // SIBLING text node said "Live" -- so the verdict depended on render
    // ordering. It passed locally and failed in CI with a count of 1, which is
    // the worst possible failure mode for a design rule: non-deterministic, and
    // pointing at the wrong element. What the rule actually means is "a span
    // whose ENTIRE text is a bare glyph, with no word of its own" -- so ask
    // that, and allow the decorative dot that legitimately sits inside a badge
    // carrying the word beside it.
    const bareDots = page.locator(
      'span:not([aria-hidden="true"]), span[aria-hidden="true"]'
    );
    const offenders: string[] = [];
    const n = await bareDots.count();
    for (let i = 0; i < n; i++) {
      const info = await bareDots.nth(i).evaluate((el) => ({
        text: (el.textContent ?? "").trim(),
        hidden: el.getAttribute("aria-hidden") === "true",
        parentText: (el.parentElement?.textContent ?? "").trim(),
        html: el.outerHTML.slice(0, 160),
      }));
      // A span that is nothing but a glyph.
      const isBareGlyph = /^[\u25CF\u25D0\u2713\u2717\u2022\u25B2\u25BC]$/.test(info.text);
      if (!isBareGlyph) continue;
      // A decorative glyph is fine IF the word it decorates is a sibling under
      // the same parent. A glyph with no word anywhere near it is the defect.
      const hasWordBeside = info.parentText.replace(info.text, "").trim().length > 0;
      if (!hasWordBeside) {
        offenders.push(
          `${info.html}  (parent text: ${JSON.stringify(info.parentText)})`
        );
      }
    }
    expect(
      offenders,
      `bare glyph with no accompanying word:\n${offenders.join("\n")}`
    ).toEqual([]);
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

    // This was INCONCLUSIVE when the page had no controls, and passed
    // vacuously -- which reads as "sizes verified" when nothing was measured.
    // PortfolioGrid added the first interactive controls (11 filter chips and a
    // Load more button), so the check is real now and is required to stay real.
    // A future refactor that removes every control must fail here rather than
    // quietly restore the vacuous pass.
    expect(
      n,
      "INCONCLUSIVE: no interactive targets found, so the 44px rule was not " +
        "exercised. If the page genuinely has no controls, delete this spec " +
        "rather than let it pass vacuously."
    ).toBeGreaterThan(0);

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
      // Walk up for the first non-transparent background. Typed as Element,
      // not HTMLElement: parentElement is Element on SVG nodes, and the walk
      // does not care which it is.
      let node: Element | null = el;
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
