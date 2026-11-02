import { parse, TYPE, type MessageFormatElement } from "@formatjs/icu-messageformat-parser";
import { describe, expect, it } from "vitest";

import az from "../../messages/az.json";
import en from "../../messages/en.json";
import ru from "../../messages/ru.json";

type Tree = { [key: string]: string | Tree };

function flatten(tree: Tree, prefix = ""): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(tree)) {
    if (typeof value === "string") out[`${prefix}${key}`] = value;
    else Object.assign(out, flatten(value, `${prefix}${key}.`));
  }
  return out;
}

const catalogues = { az: flatten(az), en: flatten(en), ru: flatten(ru) };
const keys = Object.keys(catalogues.az).sort();

/** Walks a parsed message: every argument name and every plural with its branch names. */
function inspect(elements: MessageFormatElement[]) {
  const names = new Set<string>();
  const plurals: string[][] = [];
  const visit = (nodes: MessageFormatElement[]) => {
    for (const node of nodes) {
      if (node.type === TYPE.literal || node.type === TYPE.pound) continue;
      names.add(node.value);
      if (node.type === TYPE.plural) {
        plurals.push(Object.keys(node.options).filter((option) => !option.startsWith("=")));
      }
      if (node.type === TYPE.plural || node.type === TYPE.select) {
        for (const option of Object.values(node.options)) visit(option.value);
      }
      if (node.type === TYPE.tag) visit(node.children);
    }
  };
  visit(elements);
  return { names: [...names].sort(), plurals };
}

function parsed(message: string) {
  return inspect(parse(message, { requiresOtherClause: true }));
}

/*
 * Values that are data or notation rather than prose: the language names, the Azerbaijani specimen texts and
 * sample records of /design-system, and patterns made of placeholders and punctuation only.
 */
const LANGUAGE_SPECIMENS = new Set([
  "locale.names.az",
  "designSystem.glyphs.uppercaseSource",
  "designSystem.glyphs.sentence",
  "designSystem.forms.nameValue",
  "designSystem.forms.disabledValue",
  "designSystem.table.civil",
  "designSystem.table.architecture",
  "designSystem.table.economics",
  "designSystem.table.design",
  "designSystem.navigation.subject",
  "designSystem.navigation.headerTitle",
]);
const SAMPLE_NAMES =
  /SmartAzMİU|AzMİU|ÜOMG|#məsləhət|#suallar|Mikroiqtisadiyyat|Şəhla Ağayeva|Ali riyaziyyat/g;
const AZERBAIJANI_ONLY_LETTERS = /[əƏğĞıİşŞ]/;
const CYRILLIC = /[а-яёА-ЯЁ]/;
const NO_PROSE = /^[\s\d{}/%·–—.,:()A-Za-z_-]*$/;

describe("message catalogues", () => {
  it("have exactly the keys of the Azerbaijani catalogue", () => {
    expect(Object.keys(catalogues.en).sort()).toEqual(keys);
    expect(Object.keys(catalogues.ru).sort()).toEqual(keys);
  });

  it.each(["az", "en", "ru"] as const)("%s: every message is valid ICU syntax", (locale) => {
    const broken: string[] = [];
    for (const key of keys) {
      try {
        parsed(catalogues[locale][key]!);
      } catch (error) {
        broken.push(`${key}: ${String(error)}`);
      }
    }
    expect(broken).toEqual([]);
  });

  it.each(["en", "ru"] as const)("%s: arguments match the Azerbaijani message", (locale) => {
    const different = keys.filter(
      (key) =>
        parsed(catalogues[locale][key]!).names.join() !== parsed(catalogues.az[key]!).names.join(),
    );
    expect(different).toEqual([]);
  });

  it("gives every plural the forms of its language", () => {
    const missing: string[] = [];
    const required = { az: ["other"], en: ["other"], ru: ["one", "few", "many", "other"] };
    for (const locale of ["az", "en", "ru"] as const) {
      for (const key of keys) {
        for (const forms of parsed(catalogues[locale][key]!).plurals) {
          for (const form of required[locale]) {
            if (!forms.includes(form)) missing.push(`${locale} ${key}: ${form}`);
          }
        }
      }
    }
    expect(missing).toEqual([]);
  });

  it.each(["en", "ru"] as const)("%s: no Azerbaijani-only letters outside names", (locale) => {
    const left = keys.filter((key) => {
      if (LANGUAGE_SPECIMENS.has(key)) return false;
      return AZERBAIJANI_ONLY_LETTERS.test(catalogues[locale][key]!.replace(SAMPLE_NAMES, ""));
    });
    expect(left).toEqual([]);
  });

  it("writes Russian prose in Cyrillic", () => {
    const latin = keys.filter((key) => {
      const text = catalogues.ru[key]!.replace(SAMPLE_NAMES, "");
      return !LANGUAGE_SPECIMENS.has(key) && !CYRILLIC.test(text) && !NO_PROSE.test(text);
    });
    expect(latin).toEqual([]);
  });

  it.each(["az", "en", "ru"] as const)("%s: no exclamation marks, no emoji", (locale) => {
    const loud = keys.filter((key) =>
      /!|\p{Extended_Pictographic}/u.test(catalogues[locale][key]!),
    );
    expect(loud).toEqual([]);
  });

  it("uses British spelling in English", () => {
    const american = keys.filter((key) =>
      /\b(?:center|color|colour(?!s?\b)|organiz|behavior|favorite|license\b|canceled|catalog\b|analyz|recogniz)/i.test(
        catalogues.en[key]!,
      ),
    );
    expect(american).toEqual([]);
  });

  it("keeps English sentences in sentence case", () => {
    const title = keys.filter((key) =>
      /^(?:[A-Z][a-z]+ ){2,}[A-Z][a-z]+$/.test(catalogues.en[key]!),
    );
    expect(title).toEqual([]);
  });
});
