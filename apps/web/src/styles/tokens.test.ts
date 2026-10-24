import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const webRoot = path.resolve(__dirname, "../..");
const tokensCss = readFileSync(path.join(webRoot, "src/styles/tokens.css"), "utf8");
const keycloakCss = readFileSync(
  path.join(webRoot, "../../infra/keycloak/themes/smartazmiu/login/resources/css/login.css"),
  "utf8",
);

type Tokens = Record<string, string>;

function parseBlock(css: string, selector: RegExp): Tokens {
  const match = css.match(selector);
  if (!match?.[1]) throw new Error(`block ${selector} not found`);
  const tokens: Tokens = {};
  for (const [, name, value] of match[1].matchAll(/--([a-z-]+):\s*(#[0-9a-f]{6})\s*;/gi)) {
    tokens[name!] = value!.toLowerCase();
  }
  return tokens;
}

const themes = {
  light: parseBlock(tokensCss, /:root,\s*\[data-theme="light"\]\s*\{([^}]*)\}/),
  dark: parseBlock(tokensCss, /\[data-theme="dark"\]\s*\{([^}]*)\}/),
};

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((index) => parseInt(hex.slice(index, index + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!;
}

function contrast(foreground: string, background: string): number {
  const [light, dark] = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
  return (light! + 0.05) / (dark! + 0.05);
}

const BACKGROUNDS = ["bg", "bg-subtle", "surface"];
// Text colours used on page backgrounds; WCAG AA normal text needs 4.5:1 (§12.2).
const TEXT_ON_BACKGROUND = [
  "text",
  "text-muted",
  "primary",
  "accent",
  "success",
  "warning",
  "danger",
  "info",
];
// Non-text UI that identifies a control or focus needs 3:1 (WCAG 1.4.11).
const UI_ON_BACKGROUND = ["border-control", "focus-ring"];
// Filled surfaces with their foreground.
const FILLED = [
  ["primary-contrast", "primary"],
  ["primary-contrast", "primary-hover"],
  ["primary-contrast", "accent"],
  ["primary-contrast", "danger"],
];

describe.each(Object.entries(themes))("%s theme contrast", (_theme, tokens) => {
  it.each(TEXT_ON_BACKGROUND.flatMap((fg) => BACKGROUNDS.map((bg) => [fg, bg])))(
    "%s on %s reaches 4.5:1",
    (fg, bg) => {
      expect(contrast(tokens[fg]!, tokens[bg]!)).toBeGreaterThanOrEqual(4.5);
    },
  );

  it.each(UI_ON_BACKGROUND.flatMap((fg) => BACKGROUNDS.map((bg) => [fg, bg])))(
    "%s on %s reaches 3:1",
    (fg, bg) => {
      expect(contrast(tokens[fg]!, tokens[bg]!)).toBeGreaterThanOrEqual(3);
    },
  );

  it.each(FILLED)("%s on %s reaches 4.5:1", (fg, bg) => {
    expect(contrast(tokens[fg]!, tokens[bg]!)).toBeGreaterThanOrEqual(4.5);
  });
});

describe("token definitions", () => {
  it("defines the same tokens in both themes", () => {
    expect(Object.keys(themes.dark).sort()).toEqual(Object.keys(themes.light).sort());
  });

  it("keeps the §12.2 values", () => {
    expect(themes.light.primary).toBe("#1f3a5f");
    expect(themes.dark.bg).toBe("#0f141a");
    expect(themes.light.accent).toBe("#8a6d1f");
  });
});

describe("Keycloak login theme", () => {
  const keycloakLight = parseBlock(keycloakCss, /:root\s*\{([^}]*)\}/);
  const keycloakDark = parseBlock(
    keycloakCss,
    /prefers-color-scheme:\s*dark\)\s*\{\s*:root\s*\{([^}]*)\}/,
  );

  it.each([
    ["light", keycloakLight],
    ["dark", keycloakDark],
  ] as const)("mirrors the %s token values", (theme, mirrored) => {
    expect(Object.keys(mirrored).length).toBeGreaterThan(10);
    for (const [name, value] of Object.entries(mirrored)) {
      expect({ name, value }).toEqual({ name, value: themes[theme][name] });
    }
  });
});
