import { expect, test } from "@playwright/test";

/*
 * Sprint 15, Group A: the specimens in English and Russian, in both themes at 1440 and 320 px (D-113). Russian has
 * the longest strings, so a representative set of sections is enough to see wrapping and overflow. The sections are
 * picked by position; the baselines of the Azerbaijani specimens (design-system.visual.spec.ts) are not touched.
 */
const SECTIONS = [
  { index: 1, name: "typography" },
  { index: 2, name: "glyphs" },
  { index: 4, name: "forms" },
  { index: 6, name: "notices" },
  { index: 9, name: "states" },
  { index: 10, name: "chat" },
  { index: 22, name: "gpa" },
  { index: 28, name: "assignment" },
  { index: 31, name: "offline-notices" },
  { index: 32, name: "offline-page" },
] as const;

const VIEWPORTS = [
  { prefix: "", size: null },
  { prefix: "phone-", size: { width: 320, height: 640 } },
] as const;

for (const locale of ["en", "ru"] as const) {
  for (const { prefix, size } of VIEWPORTS) {
    test(`${locale} design system sections match their ${prefix ? "phone " : ""}baselines`, async ({
      page,
      baseURL,
    }) => {
      test.setTimeout(120_000);
      if (size) await page.setViewportSize(size);
      await page.context().addCookies([{ name: "NEXT_LOCALE", value: locale, url: baseURL! }]);
      await page.goto("/design-system");
      await expect(page.locator("html")).toHaveAttribute("lang", locale);
      await page.evaluate(() => {
        document.querySelector<HTMLElement>("body > div > header")!.style.position = "static";
      });
      await page.evaluate(() => document.fonts.ready);
      for (const theme of ["light", "dark"] as const) {
        const sections = page.locator(`div[data-theme="${theme}"] section:has(> h2)`);
        expect(await sections.count()).toBeGreaterThan(SECTIONS.at(-1)!.index);
        for (const { index, name } of SECTIONS) {
          await expect(sections.nth(index)).toHaveScreenshot(
            `${locale}-${prefix}${theme}-${String(index).padStart(2, "0")}-${name}.png`,
          );
        }
      }
    });
  }
}
