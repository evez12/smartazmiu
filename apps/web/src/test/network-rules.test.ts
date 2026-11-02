/**
 * Static guard for §13.6: a button that calls the server must be switched off while offline. A control says what it
 * needs (`network="required" | "local"`), and `networkDefault` decides when it says nothing; this test reads every
 * Button in the source and fails when a button that visibly calls a mutation would stay enabled offline.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { networkDefault } from "@/components/ui/button";

const srcRoot = path.resolve(__dirname, "..");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) return sourceFiles(full);
    return /\.tsx$/.test(entry) && !/\.test\.tsx$/.test(entry) ? [full] : [];
  });
}

type ButtonTag = { where: string; tag: string };

const buttons: ButtonTag[] = sourceFiles(srcRoot).flatMap((file) => {
  const text = readFileSync(file, "utf8");
  const where = path.relative(srcRoot, file).replaceAll("\\", "/");
  return [...text.matchAll(/<Button\b((?:[^<>]|=>|\{[^}]*\})*?)>/gs)].map((match) => ({
    where: `${where}:${text.slice(0, match.index).split("\n").length}`,
    tag: match[0],
  }));
});

function describeTag(tag: string) {
  const variant = tag.match(/variant="([\w-]+)"/)?.[1] as Parameters<
    typeof networkDefault
  >[0]["variant"];
  const explicit = tag.match(/network="(required|local)"/)?.[1] as "required" | "local" | undefined;
  return {
    explicit,
    asChild: /\basChild\b/.test(tag),
    calls: /\.mutate(Async)?\(/.test(tag),
    needs:
      explicit ??
      networkDefault({
        type: tag.includes('type="submit"') ? "submit" : undefined,
        variant,
        loading: /\bloading=/.test(tag) ? false : undefined,
      }),
  };
}

describe("buttons and the network (§13.6)", () => {
  it("finds the buttons it is supposed to check", () => {
    expect(buttons.length).toBeGreaterThan(150);
  });

  it("never leaves a button that calls a mutation enabled while offline", () => {
    const open = buttons.filter(({ tag }) => {
      const info = describeTag(tag);
      return info.calls && !info.asChild && info.needs === "local";
    });
    expect(open.map(({ where }) => where)).toEqual([]);
  });

  it("keeps `local` for the few buttons that show progress but do not call the server", () => {
    // The chat composer queues what is written offline (§13.2, D-064); everything else that shows progress is a call.
    const local = buttons.filter(({ tag }) => {
      const info = describeTag(tag);
      return info.explicit === "local" && /\bloading=/.test(tag);
    });
    expect(local.map(({ where }) => where.split(":")[0])).toEqual([]);
  });

  it('allows `network="local"` on a main action only in the places that were decided', () => {
    const decided = new Set(["features/chat/composer.tsx"]);
    const exempt = buttons
      .filter(({ tag }) => {
        const info = describeTag(tag);
        return (
          info.explicit === "local" &&
          /variant="(primary|destructive|destructive-solid)"|type="submit"/.test(tag)
        );
      })
      .map(({ where }) => where.split(":")[0]!)
      .filter((file) => !decided.has(file));
    expect(exempt).toEqual([]);
  });

  it("keeps every component that follows the connection a client component", () => {
    // A server component cannot call a hook; the unit tests would not notice, the production build does.
    const offenders = sourceFiles(srcRoot)
      .filter((file) => {
        const text = readFileSync(file, "utf8");
        return /use(OfflineLock|Network)\(/.test(text) && !text.startsWith('"use client"');
      })
      .map((file) => path.relative(srcRoot, file).replaceAll("\\", "/"));
    expect(offenders).toEqual([]);
  });

  it("keeps `buttonVariants` out of the client component, so a server page can put it on a link", () => {
    const component = readFileSync(path.join(srcRoot, "components/ui/button.tsx"), "utf8");
    expect(component).not.toMatch(/export const buttonVariants/);
    const classes = readFileSync(path.join(srcRoot, "components/ui/button-variants.ts"), "utf8");
    expect(classes).not.toMatch(/use client|from "react"/);
  });
});
