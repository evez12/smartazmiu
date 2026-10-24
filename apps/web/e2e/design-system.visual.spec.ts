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

// One screenshot per specimen section and theme keeps every baseline small and diffs easy to read.
test("design system sections match their baselines", async ({ page }) => {
  await page.goto("/design-system");
  await page.evaluate(() => document.fonts.ready);
  for (const theme of ["light", "dark"] as const) {
    const sections = page.locator(`div[data-theme="${theme}"] section:has(> h2)`);
    const count = await sections.count();
    expect(count).toBeGreaterThan(8);
    for (let index = 0; index < count; index += 1) {
      const section = sections.nth(index);
      const title = slug(await section.locator("> h2").innerText());
      await expect(section).toHaveScreenshot(
        `${theme}-${String(index).padStart(2, "0")}-${title}.png`,
      );
    }
  }
});
