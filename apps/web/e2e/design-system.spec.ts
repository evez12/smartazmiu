import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const viewports = [
  { width: 320, height: 800 },
  { width: 1440, height: 900 },
];

for (const colorScheme of ["light", "dark"] as const) {
  for (const viewport of viewports) {
    test.describe(`design system · ${colorScheme} · ${viewport.width}px`, () => {
      test.use({ colorScheme, viewport });

      test("has no serious accessibility violations and no sideways scroll", async ({ page }) => {
        await page.goto("/design-system");
        await expect(page.getByRole("heading", { level: 1, name: "Dizayn sistemi" })).toBeVisible();

        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - window.innerWidth,
        );
        expect(overflow).toBe(0);

        const { violations } = await new AxeBuilder({ page }).analyze();
        const serious = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
        expect(serious.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
      });
    });
  }
}

test("renders the Azerbaijani alphabet in IBM Plex Sans at every weight", async ({ page }) => {
  await page.goto("/design-system");
  await page.evaluate(() => document.fonts.ready);
  const loaded = await page.evaluate(() =>
    ["400", "500", "600"].map((weight) =>
      document.fonts.check(`${weight} 16px "IBM Plex Sans"`, "ƏəİıŞşĞğÇçÖöÜü"),
    ),
  );
  expect(loaded).toEqual([true, true, true]);
  // innerText reflects CSS text-transform, so this checks the browser's Azerbaijani casing rules.
  await expect(page.locator('[lang="az"].uppercase').first()).toHaveText(/İSTİFADƏÇİ, ISPANAQ/, {
    useInnerText: true,
  });
});

test("keyboard users can operate dialogs and menus", async ({ page }) => {
  await page.goto("/design-system");
  const openDialog = page.getByRole("button", { name: "Dialoqu açın" });
  await openDialog.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Bildiriş ayarları" });
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(openDialog).toBeFocused();

  const menuTrigger = page.getByRole("button", { name: "Menyunu açın" });
  await menuTrigger.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("menuitem", { name: "Cavab yazın" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(menuTrigger).toBeFocused();
});

test("theme switch applies the dark tokens", async ({ page }) => {
  await page.goto("/design-system");
  await page.getByRole("radio", { name: "Tünd" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const background = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(background).toBe("rgb(15, 20, 26)");
});
