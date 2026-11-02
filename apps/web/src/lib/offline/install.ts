/**
 * When to offer installing the app (§12.6): never on the first visit, never after it was dismissed or installed,
 * and only where the browser can install it or the user must be told how. These markers are browser preferences,
 * not account data, so a wipe leaves them alone.
 */
const VISITS_KEY = "sa:install:visits";
const DISMISSED_KEY = "sa:install:dismissed";
const COUNTED_KEY = "sa:install:counted";

export const VISITS_BEFORE_OFFER = 2;

/** Counts this browser session once (a tab opened later in the same session does not count again). */
export function recordVisit(): number {
  try {
    const visits = Number(localStorage.getItem(VISITS_KEY) ?? "0");
    if (sessionStorage.getItem(COUNTED_KEY)) return visits;
    sessionStorage.setItem(COUNTED_KEY, "1");
    localStorage.setItem(VISITS_KEY, String(visits + 1));
    return visits + 1;
  } catch {
    return 0;
  }
}

export function isDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISSED_KEY) !== null;
  } catch {
    return true;
  }
}

export function rememberDismissed(): void {
  try {
    localStorage.setItem(DISMISSED_KEY, String(Date.now()));
  } catch {
    // Storage blocked: the prompt may come back on the next visit, which is harmless.
  }
}

export function isStandalone(): boolean {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

/** Safari on iOS has no install event; the user adds the app from the share menu. */
export function isIosSafari(userAgent: string): boolean {
  return /iPhone|iPad|iPod/.test(userAgent) && !/CriOS|FxiOS|EdgiOS/.test(userAgent);
}

export function shouldOffer(state: {
  visits: number;
  dismissed: boolean;
  standalone: boolean;
  canPrompt: boolean;
  ios: boolean;
}): boolean {
  return (
    state.visits >= VISITS_BEFORE_OFFER &&
    !state.dismissed &&
    !state.standalone &&
    (state.canPrompt || state.ios)
  );
}
