/**
 * Static guards for the §12 rules that are easy to break by accident and hard to spot in review.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const srcRoot = path.resolve(__dirname, "..");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) return sourceFiles(full);
    return /\.(tsx?|css)$/.test(entry) && !/\.test\.tsx?$/.test(entry) ? [full] : [];
  });
}

const files = sourceFiles(srcRoot).map((file) => ({
  file: path.relative(srcRoot, file).replaceAll("\\", "/"),
  text: readFileSync(file, "utf8"),
}));

// Class-name rules apply to components; globals.css legitimately names the utilities it disables.
const componentFiles = files.filter(({ file }) => /\.tsx?$/.test(file));

function offenders(
  pattern: RegExp,
  allow: (file: string) => boolean = () => false,
  scope = componentFiles,
) {
  return scope
    .filter(({ file }) => !allow(file))
    .flatMap(({ file, text }) =>
      [...text.matchAll(pattern)].map((match) => `${file}: ${match[0]}`),
    );
}

describe("design rules", () => {
  it("keeps colour values in tokens.css only", () => {
    expect(
      offenders(
        /#[0-9a-fA-F]{3,8}\b(?![\w-])|rgba?\(|hsla?\(|oklch\(/g,
        (file) => file === "styles/tokens.css",
        files,
      ),
    ).toEqual([]);
  });

  it("uses no gradients, blur or glow effects", () => {
    expect(offenders(/gradient|backdrop-blur|blur-|drop-shadow|glow/g)).toEqual([]);
  });

  it("uses only the overlay shadow", () => {
    expect(offenders(/\bshadow-(?!overlay\b)[\w[\]-]+/g)).toEqual([]);
  });

  it("never rounds more than 6 px (avatars and radio dots are circular)", () => {
    const allowed = /^rounded-(?:(?:[trblxyse]{1,2})-)?(?:control|panel|full|\[2px\])$/;
    const radii = offenders(/\brounded(?:-[\w[\]-]+)?/g).filter(
      (entry) => !allowed.test(entry.split(": ")[1] ?? ""),
    );
    expect(radii).toEqual([]);
  });

  it("uses no letter-spaced labels or scale-on-hover effects", () => {
    expect(offenders(/\btracking-(?!normal)\w+|hover:scale|animate-bounce/g)).toEqual([]);
  });

  it("imports Radix primitives only inside the component layer", () => {
    expect(offenders(/from "radix-ui"/g, (file) => file.startsWith("components/"))).toEqual([]);
  });

  it("uses no emoji in UI chrome", () => {
    expect(offenders(/\p{Extended_Pictographic}/gu)).toEqual([]);
  });
});
