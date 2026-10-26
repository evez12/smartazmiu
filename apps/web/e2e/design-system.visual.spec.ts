import { expect, test } from "@playwright/test";

const ASCII_FOLD: Record<string, string> = {
  ə: "e",
  ı: "i",
  ö: "o",
  ü: "u",
  ç: "c",
  ş: "s",
  ğ: "g",
};

function slug(heading: string): string {
  return heading
    .toLocaleLowerCase("az")
    .replace(/[əıöüçşğ]/g, (letter) => ASCII_FOLD[letter] ?? letter)
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

// One screenshot per specimen section and theme keeps every baseline small and diffs easy to read. The phone pass
// (320 px, the narrowest supported width, §12.6) stacks the two themes and lays the tables out as stacked rows.
const VIEWPORTS = [
  { prefix: "", size: null },
  { prefix: "phone-", size: { width: 320, height: 640 } },
] as const;

for (const { prefix, size } of VIEWPORTS) {
  test(`design system sections match their ${prefix ? "phone " : ""}baselines`, async ({
    page,
  }) => {
    if (size) await page.setViewportSize(size);
    await page.goto("/design-system");
    // The sticky page header would otherwise be captured on top of whatever section is scrolled under it.
    await page.evaluate(() => {
      document.querySelector<HTMLElement>("body > div > header")!.style.position = "static";
    });
    await page.evaluate(() => document.fonts.ready);
    for (const theme of ["light", "dark"] as const) {
      const sections = page.locator(`div[data-theme="${theme}"] section:has(> h2)`);
      const count = await sections.count();
      expect(count).toBeGreaterThan(8);
      for (let index = 0; index < count; index += 1) {
        const section = sections.nth(index);
        const title = slug(await section.locator("> h2").innerText());
        await expect(section).toHaveScreenshot(
          `${prefix}${theme}-${String(index).padStart(2, "0")}-${title}.png`,
        );
      }
    }
  });
}
