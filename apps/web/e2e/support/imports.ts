import path from "node:path";

import { expect, type Page } from "@playwright/test";

import { hydrated, openPage } from "./auth";

export const SEED_DIR = path.resolve(__dirname, "../../../../infra/seed/academics");

type KindOption = { label: string } | { value: string };
type UploadedFile = { name: string; content: string };

/**
 * Chooses the file on the upload step of the import wizard. The picker is matched by its label, inside the page's
 * main landmark, and only once the page has hydrated: a file chosen on server-rendered markup is silently lost.
 */
export async function chooseImportFile(page: Page, file: string | UploadedFile) {
  await hydrated(page);
  await page
    .getByRole("main")
    .getByLabel(/^Fayl/)
    .and(page.locator("input[type=file]"))
    .setInputFiles(
      typeof file === "string"
        ? file
        : { name: file.name, mimeType: "text/csv", buffer: Buffer.from(file.content) },
    );
}

/**
 * Validates and applies one file through the import wizard, as the dean's office would. A seed file applied
 * before (by another test or run) applies again as a no-op.
 */
export async function importFile(page: Page, kind: KindOption, file: string | UploadedFile) {
  const name = typeof file === "string" ? path.basename(file) : file.name;
  await openPage(page, "/admin/imports/new");
  await page.getByRole("combobox", { name: /Məlumat növü/ }).selectOption(kind);
  await chooseImportFile(page, file);
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
