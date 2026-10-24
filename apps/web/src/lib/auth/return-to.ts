/**
 * Accepts only same-origin absolute paths, so a crafted `returnTo` cannot send users to another site
 * after sign-in (open redirect).
 */
export function safeReturnTo(value: string | null | undefined, fallback = "/"): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) {
    return fallback;
  }
  if (/[\u0000-\u001f]/.test(value)) return fallback;
  try {
    const parsed = new URL(value, "http://same-origin.invalid");
    if (parsed.origin !== "http://same-origin.invalid") return fallback;
    if (parsed.pathname.startsWith("/auth/")) return fallback;
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return fallback;
  }
}
