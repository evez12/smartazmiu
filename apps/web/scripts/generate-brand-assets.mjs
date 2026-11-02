/**
 * Generates the favicon, the PWA icons and the theme colours the manifest needs from the placeholder brand
 * (`src/components/brand/brand.ts`) and the design tokens (`src/styles/tokens.css`), so no colour or letter is
 * written down twice. Run with `pnpm brand` after changing either; the results are committed.
 */
import { chromium } from "@playwright/test";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { MONOGRAM } from "../src/components/brand/brand.ts";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const tokens = readFileSync(path.join(root, "src/styles/tokens.css"), "utf8");

function tokenValues(selector) {
  const block = tokens.split(selector)[1]?.split("}")[0] ?? "";
  return Object.fromEntries(
    [...block.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)].map((m) => [m[1], m[2]]),
  );
}
const light = tokenValues(':root,\n[data-theme="light"] {');
const dark = tokenValues('[data-theme="dark"] {');

const font = readFileSync(
  path.join(
    root,
    "node_modules/@fontsource/ibm-plex-sans/files/ibm-plex-sans-latin-600-normal.woff2",
  ),
).toString("base64");

/** One square tile with the monogram; `letter` is the font size in pixels. */
function tileHtml({ size, radius, letter }) {
  return `<!doctype html><meta charset="utf-8"><style>
@font-face{font-family:Plex;font-weight:600;src:url(data:font/woff2;base64,${font}) format("woff2")}
html,body{margin:0;background:transparent}
div{width:${size}px;height:${size}px;border-radius:${radius}px;background:${light.primary};color:${light["primary-contrast"]};
display:flex;align-items:center;justify-content:center;font:600 ${letter}px/1 Plex,sans-serif}
</style><div>${MONOGRAM}</div>`;
}

const icons = [
  { file: "icons/icon-192.png", size: 192, radius: 24, letter: 112 },
  { file: "icons/icon-512.png", size: 512, radius: 64, letter: 300 },
  // Full bleed with the letter inside the central 60 %: the platform applies its own mask.
  { file: "icons/maskable-512.png", size: 512, radius: 0, letter: 230 },
  { file: "icons/apple-touch-icon.png", size: 180, radius: 0, letter: 104 },
];

mkdirSync(path.join(root, "public/icons"), { recursive: true });
const browser = await chromium.launch();
try {
  for (const icon of icons) {
    const page = await browser.newPage({ viewport: { width: icon.size, height: icon.size } });
    await page.setContent(tileHtml(icon));
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({
      path: path.join(root, "public", icon.file),
      omitBackground: true,
      clip: { x: 0, y: 0, width: icon.size, height: icon.size },
    });
    await page.close();
  }
} finally {
  await browser.close();
}

writeFileSync(
  path.join(root, "public/icon.svg"),
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="4" fill="${light.primary}"/><text x="16" y="22.5" font-family="IBM Plex Sans, system-ui, sans-serif" font-size="18" font-weight="600" text-anchor="middle" fill="${light["primary-contrast"]}">${MONOGRAM}</text></svg>\n`,
);

const colours = {
  light: { background: light.bg, surface: light.surface },
  dark: { background: dark.bg, surface: dark.surface },
};
writeFileSync(
  path.join(root, "src/lib/pwa/theme-colours.json"),
  `${JSON.stringify(colours, null, 2)}\n`,
);
