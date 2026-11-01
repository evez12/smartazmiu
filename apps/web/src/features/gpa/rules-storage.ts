import { GPA_DEFAULTS, type GpaConfig } from "./uomg";

/** Per-viewer convenience only (D-107): never required, never sent to the server, and it may be missing or blocked. */
const STORAGE_KEY = "smartazmiu:gpa-rules:v1";

function inRange(value: unknown, min: number, max: number): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= min && value <= max;
}

/** Accepts only a complete, well-formed set of rules; anything else (an old shape, a hand edit) is ignored. */
export function parseRules(value: unknown): GpaConfig | null {
  if (typeof value !== "object" || value === null) return null;
  const rules = value as Record<string, unknown>;
  if (typeof rules.includeFailed !== "boolean") return null;
  if (rules.retakePolicy !== "replace" && rules.retakePolicy !== "average") return null;
  if (!inRange(rules.roundDigits, 0, 3)) return null;
  if (!inRange(rules.minExamScore, 0, 50)) return null;
  if (!inRange(rules.passThreshold, 0, 100)) return null;
  return {
    includeFailed: rules.includeFailed,
    retakePolicy: rules.retakePolicy,
    roundDigits: rules.roundDigits,
    minExamScore: rules.minExamScore,
    passThreshold: rules.passThreshold,
  };
}

export function loadRules(): GpaConfig | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw === null ? null : parseRules(JSON.parse(raw));
  } catch {
    return null;
  }
}

/** Defaults are stored as nothing, so a later change of the defaults reaches people who never changed them. */
export function saveRules(rules: GpaConfig): void {
  try {
    const isDefault = (Object.keys(GPA_DEFAULTS) as (keyof GpaConfig)[]).every(
      (key) => rules[key] === GPA_DEFAULTS[key],
    );
    if (isDefault) window.localStorage.removeItem(STORAGE_KEY);
    else window.localStorage.setItem(STORAGE_KEY, JSON.stringify(rules));
  } catch {
    // Private window, blocked or full storage: the rules just apply for this visit.
  }
}
