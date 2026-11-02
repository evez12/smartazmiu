// Service worker: Web Push (D-049) and the offline shell (D-117).
//
// It keeps static files and one user-independent page, and nothing else: no API response, no HTML of a signed-in
// page and no token ever goes into Cache Storage. The data that is shown offline lives in IndexedDB, written by
// the page for the signed-in user (`src/lib/offline`).
// Replaced with the build id when `/sw.js` is served (`src/app/sw.js/route.ts`), so every deploy changes the bytes
// and open pages find out about it.
const VERSION = "__BUILD_ID__";
const CACHE_PREFIX = "sa-";
const SHELL_CACHE = `${CACHE_PREFIX}shell-${VERSION}`;
const STATIC_CACHE = `${CACHE_PREFIX}static-${VERSION}`;
const SHELL_URL = "/offline";
// The development server serves changing code under the same address; caching it would show stale pages.
const CACHING = VERSION !== "development";

function isStaticAsset(url) {
  return (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/icons/") ||
    url.pathname === "/icon.svg"
  );
}

/** A response that says `no-store` is never kept, whatever asked for it. */
function mayStore(response) {
  return response.ok && !/\bno-store\b/i.test(response.headers.get("cache-control") ?? "");
}

function staticAssetUrls(text, base) {
  const found = new Set();
  for (const match of text.matchAll(/\/_next\/static\/[^"'\\\s<>)]+/g)) {
    found.add(new URL(match[0], base).href);
  }
  return found;
}

/** Fonts a stylesheet refers to, resolved against the stylesheet's own address. */
function fontUrls(css, base) {
  const found = new Set();
  for (const match of css.matchAll(/url\(["']?([^"')]+\.woff2)["']?\)/g)) {
    found.add(new URL(match[1], base).href);
  }
  return found;
}

async function keep(cache, url) {
  const response = await fetch(url, { credentials: "same-origin" });
  if (mayStore(response)) await cache.put(url, response.clone());
  return response;
}

/**
 * Stores the offline page and the scripts, styles and fonts it needs. The page is fetched with the browser's
 * cookies so it comes in the chosen language; it contains no user data (it is the same for everyone).
 */
async function precacheShell() {
  const response = await fetch(SHELL_URL, { credentials: "same-origin", cache: "reload" });
  const isHtml = (response.headers.get("content-type") ?? "").includes("text/html");
  if (!mayStore(response) || !isHtml) return false;
  const html = await response.clone().text();
  await (await caches.open(SHELL_CACHE)).put(SHELL_URL, response);

  const assets = await caches.open(STATIC_CACHE);
  const scripts = staticAssetUrls(html, self.location.origin);
  await Promise.all(
    [...scripts].map(async (url) => {
      const asset = await keep(assets, url);
      if (!url.endsWith(".css")) return;
      const fonts = fontUrls(await asset.clone().text(), url);
      await Promise.all([...fonts].map((font) => keep(assets, font)));
    }),
  );
  return true;
}

async function navigate(request) {
  try {
    return await fetch(request);
  } catch (error) {
    const shell = await (await caches.open(SHELL_CACHE)).match(SHELL_URL, { ignoreVary: true });
    if (shell) return shell;
    throw error;
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(STATIC_CACHE);
  const cached = await cache.match(request, { ignoreVary: true });
  if (cached) return cached;
  const response = await fetch(request);
  if (mayStore(response)) await cache.put(request, response.clone());
  return response;
}

self.addEventListener("install", () => {
  // A new version waits until the page asks for it (`SKIP_WAITING`), so a reload never happens under the user.
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const current = new Set([SHELL_CACHE, STATIC_CACHE]);
      const names = await caches.keys();
      await Promise.all(
        names
          .filter((n) => n.startsWith(CACHE_PREFIX) && !current.has(n))
          .map((n) => caches.delete(n)),
      );
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
  if (event.data?.type === "PRECACHE_SHELL") {
    // The page waits for the answer before it remembers that the shell is stored.
    const answer = (stored) => event.ports[0]?.postMessage(stored);
    event.waitUntil(
      (CACHING ? precacheShell() : Promise.resolve(false)).then(answer, () => answer(false)),
    );
  }
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (!CACHING || request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (request.mode === "navigate") {
    event.respondWith(navigate(request));
  } else if (isStaticAsset(url)) {
    event.respondWith(cacheFirst(request));
  }
});

self.addEventListener("push", (event) => {
  if (!event.data) return;
  const message = event.data.json();
  event.waitUntil(
    self.registration.showNotification(message.title, {
      body: message.body,
      icon: "/icons/icon-192.png",
      lang: "az",
      tag: message.tag,
      data: { url: message.url },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = new URL(event.notification.data?.url ?? "/", self.location.origin);
  // Only same-origin paths: the payload comes from our server, but a link never leaves the site.
  const target = url.origin === self.location.origin ? url.href : self.location.origin;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      const open = windows.find((client) => client.url === target);
      return open ? open.focus() : self.clients.openWindow(target);
    }),
  );
});
