/**
 * Content Security Policy (§14): scripts only with the per-request nonce, no framing, no plugins.
 * Inline `style` attributes stay allowed because Radix positions popovers with them.
 */
export function contentSecurityPolicy({
  nonce,
  isDev,
  isHttps,
  socketUrl = "",
  storageUrl = "",
}: {
  nonce: string;
  isDev: boolean;
  isHttps: boolean;
  /** The chat WebSocket (§5.9); listed explicitly because not every browser counts ws: as 'self'. */
  socketUrl?: string;
  /** Attachment storage on another origin (native development only, D-068). */
  storageUrl?: string;
}): string {
  const socketOrigin = socketUrl ? new URL(socketUrl).origin.replace(/^http/, "ws") : "";
  const storage = storageUrl ? ` ${new URL(storageUrl).origin}` : "";
  const directives = [
    "default-src 'self'",
    // React needs eval for dev-only debugging features; production never does.
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
    `style-src 'self' 'nonce-${nonce}'`,
    "style-src-attr 'unsafe-inline'",
    `img-src 'self' blob: data:${storage}`,
    "font-src 'self'",
    // The push service worker (`public/sw.js`); without this it would fall back to the nonce-only script-src.
    "worker-src 'self'",
    `connect-src 'self'${storage}${socketOrigin ? ` ${socketOrigin}` : ""}${isDev ? " ws: wss:" : ""}`,
    // PDF previews open in a frame (§5.3); attachments are served from the app's origin behind nginx.
    `frame-src 'self'${storage}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ];
  if (isHttps) directives.push("upgrade-insecure-requests");
  return directives.join("; ");
}
