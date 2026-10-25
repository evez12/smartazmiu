import path from "node:path";

import { expect, type Page } from "@playwright/test";

import { openPage } from "./auth";

export const SEED_DIR = path.resolve(__dirname, "../../../../infra/seed/academics");

type KindOption = { label: string } | { value: string };
type UploadedFile = { name: string; content: string };

/**
 * Validates and applies one file through the import wizard, as the dean's office would. A seed file applied
 * before (by another test or run) applies again as a no-op.
 */
export async function importFile(page: Page, kind: KindOption, file: string | UploadedFile) {
  const name = typeof file === "string" ? path.basename(file) : file.name;
  await openPage(page, "/admin/imports/new");
  await page.getByRole("combobox", { name: /Məlumat növü/ }).selectOption(kind);
  await page
    .getByLabel(/^Fayl/, { exact: false })
    .and(page.locator("input[type=file]"))
    .setInputFiles(
      typeof file === "string"
        ? file
        : { name, mimeType: "text/csv", buffer: Buffer.from(file.content) },
    );
  await page.getByRole("button", { name: "Faylı yoxlayın" }).click();

  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  await expect(
    page
      .getByText("Fayl yoxlanıldı, xəta tapılmadı")
      .or(page.getByText("Bu fayl artıq tətbiq olunub")),
  ).toBeVisible();
  await page.getByRole("button", { name: "Tətbiq edin" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Tətbiq edin" }).click();
  await expect(page.getByText("İdxal tətbiq olunub")).toBeVisible();
}
