import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it, vi } from "vitest";

import colours from "./theme-colours.json";

vi.mock("next-intl/server", () => ({
  getTranslations: async () => (key: string) => `meta.${key}`,
  getLocale: async () => "ru",
}));

const root = path.resolve(__dirname, "../../..");
const tokens = readFileSync(path.join(root, "src/styles/tokens.css"), "utf8");

function token(theme: "light" | "dark", name: string): string {
  const block =
    theme === "light"
      ? (tokens.split(':root,\n[data-theme="light"] {')[1] ?? "")
      : (tokens.split('[data-theme="dark"] {')[1] ?? "");
  const match = block.split("}")[0]!.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`));
  if (!match) throw new Error(`Token ${name} not found`);
  return match[1]!;
}

/** Width and height from the PNG header, so an icon of the wrong size is caught without an image library. */
function pngSize(file: string): { width: number; height: number } {
  const bytes = readFileSync(path.join(root, "public", file));
  expect(bytes.subarray(1, 4).toString("latin1")).toBe("PNG");
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

describe("theme colours", () => {
  it("are the design tokens, not a second copy that can drift (§12.2); run `pnpm brand` after a token change", () => {
    expect(colours).toEqual({
      light: { background: token("light", "bg"), surface: token("light", "surface") },
      dark: { background: token("dark", "bg"), surface: token("dark", "surface") },
    });
  });

  it("make the favicon the primary colour of the light theme", () => {
    const svg = readFileSync(path.join(root, "public/icon.svg"), "utf8");
    expect(svg).toContain(`fill="${token("light", "primary")}"`);
    expect(svg).toContain(`fill="${token("light", "primary-contrast")}"`);
  });
});

describe("icons", () => {
  it.each([
    ["icons/icon-192.png", 192],
    ["icons/icon-512.png", 512],
    ["icons/maskable-512.png", 512],
    ["icons/apple-touch-icon.png", 180],
  ])("%s is %i px square", (file, size) => {
    expect(pngSize(file)).toEqual({ width: size, height: size });
  });
});

describe("the web app manifest", () => {
  it("makes an installable standalone app named after the wordmark", async () => {
    const { default: manifest } = await import("@/app/manifest");
    const result = await manifest();
    expect(result).toMatchObject({
      name: "SmartAzMİU",
      short_name: "SmartAzMİU",
      display: "standalone",
      start_url: "/",
      scope: "/",
      lang: "ru",
      description: "meta.description",
      theme_color: colours.light.surface,
      background_color: colours.light.background,
    });
  });

  it("lists icons that exist, with the sizes it claims, and a maskable one", async () => {
    const { default: manifest } = await import("@/app/manifest");
    const icons = (await manifest()).icons!;
    for (const icon of icons) {
      const size = Number(icon.sizes!.split("x")[0]);
      expect(pngSize(icon.src.slice(1)), icon.src).toEqual({ width: size, height: size });
    }
    expect(icons.some((icon) => icon.purpose === "maskable")).toBe(true);
    expect(icons.some((icon) => icon.purpose === "any" && icon.sizes === "192x192")).toBe(true);
    expect(icons.some((icon) => icon.purpose === "any" && icon.sizes === "512x512")).toBe(true);
  });
});
