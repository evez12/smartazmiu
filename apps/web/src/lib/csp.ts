/**
 * Content Security Policy (§14): scripts only with the per-request nonce, no framing, no plugins.
 * Inline `style` attributes stay allowed because Radix positions popovers with them.
 */
export function contentSecurityPolicy({
  nonce,
  isDev,
  isHttps,
}: {
  nonce: string;
  isDev: boolean;
  isHttps: boolean;
}): string {
  const directives = [
    "default-src 'self'",
    // React needs eval for dev-only debugging features; production never does.
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
    `style-src 'self' 'nonce-${nonce}'`,
    "style-src-attr 'unsafe-inline'",
    "img-src 'self' blob: data:",
    "font-src 'self'",
    `connect-src 'self'${isDev ? " ws: wss:" : ""}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ];
  if (isHttps) directives.push("upgrade-insecure-requests");
  return directives.join("; ");
}
