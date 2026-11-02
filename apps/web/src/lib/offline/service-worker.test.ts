import { readFileSync } from "node:fs";
import path from "node:path";
import vm from "node:vm";

import { describe, expect, it, vi } from "vitest";

import { renderServiceWorker } from "./service-worker-source";

const SOURCE = readFileSync(path.resolve(__dirname, "../../../public/sw-core.js"), "utf8");
const ORIGIN = "https://smartazmiu.test";

type Listener = (event: Record<string, unknown>) => void;

/** A Cache Storage whose entries can be inspected: name -> url -> response. */
class FakeCaches {
  readonly stores = new Map<string, Map<string, Response>>();
  async open(name: string) {
    const store = this.stores.get(name) ?? new Map<string, Response>();
    this.stores.set(name, store);
    const keyOf = (request: Request | string) =>
      typeof request === "string" ? request : request.url;
    const absolute = (key: string) => new URL(key, ORIGIN).href;
    return {
      put: async (request: Request | string, response: Response) => {
        store.set(absolute(keyOf(request)), response);
      },
      match: async (request: Request | string) => store.get(absolute(keyOf(request))),
    };
  }
  async keys() {
    return [...this.stores.keys()];
  }
  async delete(name: string) {
    return this.stores.delete(name);
  }
}

function html(body: string, headers: Record<string, string> = {}) {
  return new Response(body, { headers: { "content-type": "text/html", ...headers } });
}

function startWorker(buildId: string, fetchImpl: (url: string) => Promise<Response>) {
  const listeners: Record<string, Listener> = {};
  const caches = new FakeCaches();
  const skipWaiting = vi.fn();
  const claim = vi.fn(async () => undefined);
  const scope = {
    location: new URL(`${ORIGIN}/sw.js`),
    clients: { claim, matchAll: async () => [], openWindow: vi.fn() },
    registration: { showNotification: vi.fn() },
    skipWaiting,
    addEventListener: (type: string, listener: Listener) => {
      listeners[type] = listener;
    },
  };
  const context = vm.createContext({
    self: scope,
    caches,
    URL,
    Response,
    fetch: (input: string | Request) => fetchImpl(typeof input === "string" ? input : input.url),
  });
  vm.runInContext(renderServiceWorker(SOURCE, buildId), context);
  const waits: Promise<unknown>[] = [];
  const dispatch = (type: string, event: Record<string, unknown> = {}) => {
    listeners[type]!({ waitUntil: (promise: Promise<unknown>) => waits.push(promise), ...event });
    return Promise.all(waits);
  };
  /** Dispatches a fetch event and says whether the worker took the request over. */
  const handles = (url: string, init: { mode?: string; method?: string } = {}) => {
    const respondWith = vi.fn();
    listeners.fetch!({
      request: { url, method: init.method ?? "GET", mode: init.mode ?? "no-cors" },
      respondWith,
    });
    return {
      taken: respondWith.mock.calls.length > 0,
      answer: respondWith.mock.calls[0]?.[0] as Promise<Response>,
    };
  };
  return { caches, dispatch, handles, skipWaiting, claim };
}

const PRODUCTION = "b4k9x2";

describe("what the worker takes over", () => {
  const worker = () => startWorker(PRODUCTION, async () => new Response("ok"));

  it("takes static files and icons", () => {
    const { handles } = worker();
    expect(handles(`${ORIGIN}/_next/static/chunks/app.js`).taken).toBe(true);
    expect(handles(`${ORIGIN}/icons/icon-192.png`).taken).toBe(true);
    expect(handles(`${ORIGIN}/icon.svg`).taken).toBe(true);
  });

  it.each([
    "/api/v1/me/schedule",
    "/api/v1/me/grades",
    "/api/v1/chat/channels/c1/messages",
    "/api/v1/me/export",
    "/api/v1/chat/ws-ticket",
    "/auth/signin",
    "/smartazmiu/object-key?X-Amz-Signature=abc",
    "/ws",
    "/manifest.webmanifest",
  ])("leaves %s to the network, so API data, tokens and files never enter a cache", (pathname) => {
    const { handles } = worker();
    expect(handles(`${ORIGIN}${pathname}`).taken).toBe(false);
  });

  it("leaves other origins and non-GET requests alone", () => {
    const { handles } = worker();
    expect(handles("https://elsewhere.test/_next/static/a.js").taken).toBe(false);
    expect(handles(`${ORIGIN}/_next/static/a.js`, { method: "POST" }).taken).toBe(false);
  });

  it("does nothing in development, where the same address serves changing code", () => {
    const { handles } = startWorker("development", async () => new Response("ok"));
    expect(handles(`${ORIGIN}/_next/static/chunks/app.js`).taken).toBe(false);
    expect(handles(`${ORIGIN}/login`, { mode: "navigate" }).taken).toBe(false);
  });
});

describe("static files", () => {
  it("are fetched once and then served from the cache", async () => {
    const fetchImpl = vi.fn(
      async () =>
        new Response("script", {
          headers: { "cache-control": "public, max-age=31536000, immutable" },
        }),
    );
    const { handles, caches } = startWorker(PRODUCTION, fetchImpl);
    await (await handles(`${ORIGIN}/_next/static/chunks/app.js`).answer).text();
    const again = await handles(`${ORIGIN}/_next/static/chunks/app.js`).answer;
    expect(await again.text()).toBe("script");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect([...caches.stores.keys()]).toEqual([`sa-static-${PRODUCTION}`]);
  });

  it("are not kept when the response says no-store or failed", async () => {
    const answers = [
      new Response("secret", { headers: { "cache-control": "no-store" } }),
      new Response("missing", { status: 404 }),
    ];
    const { handles, caches } = startWorker(PRODUCTION, async () => answers.shift()!);
    await handles(`${ORIGIN}/_next/static/a.js`).answer;
    await handles(`${ORIGIN}/_next/static/b.js`).answer;
    expect([...(caches.stores.get(`sa-static-${PRODUCTION}`) ?? new Map()).keys()]).toEqual([]);
  });
});

describe("the offline shell", () => {
  const SHELL = html(
    `<script src="/_next/static/chunks/main.js"></script><link href="/_next/static/chunks/app.css">` +
      `<script>self.__next_f.push(["/_next/static/chunks/lazy.js"])</script>`,
    { "cache-control": "no-cache" },
  );

  function shellFetch(extra: Record<string, Response> = {}) {
    return vi.fn(async (url: string) => {
      const pathname = new URL(url, ORIGIN).pathname;
      if (pathname === "/offline") return SHELL.clone();
      if (pathname === "/_next/static/chunks/app.css") {
        return new Response(
          "@font-face{src:url(../media/plex.woff2) format('woff2'),url(../media/plex.woff) format('woff')}",
        );
      }
      return extra[pathname]?.clone() ?? new Response(`file ${pathname}`);
    });
  }

  it("is stored with the scripts, styles and fonts it needs when the page asks", async () => {
    const fetchImpl = shellFetch();
    const { dispatch, caches } = startWorker(PRODUCTION, fetchImpl);
    const answer = vi.fn();
    await dispatch("message", {
      data: { type: "PRECACHE_SHELL" },
      ports: [{ postMessage: answer }],
    });
    expect(answer).toHaveBeenCalledWith(true);
    expect([...caches.stores.get(`sa-shell-${PRODUCTION}`)!.keys()]).toEqual([`${ORIGIN}/offline`]);
    expect([...caches.stores.get(`sa-static-${PRODUCTION}`)!.keys()].sort()).toEqual([
      `${ORIGIN}/_next/static/chunks/app.css`,
      `${ORIGIN}/_next/static/chunks/lazy.js`,
      `${ORIGIN}/_next/static/chunks/main.js`,
      `${ORIGIN}/_next/static/media/plex.woff2`,
    ]);
  });

  it("is refused when the server marks it no-store, because nothing no-store is kept", async () => {
    const { dispatch, caches } = startWorker(PRODUCTION, async () =>
      html("page", { "cache-control": "private, no-cache, no-store" }),
    );
    const answer = vi.fn();
    await dispatch("message", {
      data: { type: "PRECACHE_SHELL" },
      ports: [{ postMessage: answer }],
    });
    expect(answer).toHaveBeenCalledWith(false);
    expect(caches.stores.get(`sa-shell-${PRODUCTION}`)).toBeUndefined();
  });

  it("is shown when a navigation fails, and only then", async () => {
    let online = true;
    const fetchImpl = shellFetch();
    const worker = startWorker(PRODUCTION, async (url) => {
      if (!online && new URL(url).pathname !== "/offline") throw new TypeError("Failed to fetch");
      return fetchImpl(url);
    });
    await worker.dispatch("message", {
      data: { type: "PRECACHE_SHELL" },
      ports: [{ postMessage: vi.fn() }],
    });

    const live = await worker.handles(`${ORIGIN}/schedule`, { mode: "navigate" }).answer;
    expect(await live.text()).toBe("file /schedule");

    online = false;
    const offline = await worker.handles(`${ORIGIN}/schedule`, { mode: "navigate" }).answer;
    expect(await offline.text()).toContain("/_next/static/chunks/main.js");
  });

  it("lets the failure through when no shell was stored, instead of showing a made-up page", async () => {
    const { handles } = startWorker(PRODUCTION, async () => {
      throw new TypeError("Failed to fetch");
    });
    await expect(handles(`${ORIGIN}/schedule`, { mode: "navigate" }).answer).rejects.toThrow(
      "Failed to fetch",
    );
  });
});

describe("versions", () => {
  it("delete the caches of other builds when the new one activates, and only the worker's own", async () => {
    const { dispatch, caches, claim } = startWorker(PRODUCTION, async () => new Response("ok"));
    for (const name of ["sa-shell-old", "sa-static-old", "sa-static-b4k9x2", "not-ours"]) {
      await caches.open(name);
    }
    await dispatch("activate");
    expect([...caches.stores.keys()].sort()).toEqual(["not-ours", "sa-static-b4k9x2"]);
    expect(claim).toHaveBeenCalled();
  });

  it("wait for the page before taking over", async () => {
    const { dispatch, skipWaiting } = startWorker(PRODUCTION, async () => new Response("ok"));
    await dispatch("install");
    expect(skipWaiting).not.toHaveBeenCalled();
    await dispatch("message", { data: { type: "SKIP_WAITING" }, ports: [] });
    expect(skipWaiting).toHaveBeenCalledTimes(1);
  });

  it("carry the build id into the script, so every deploy changes its bytes", () => {
    expect(renderServiceWorker(SOURCE, "one")).not.toBe(renderServiceWorker(SOURCE, "two"));
    expect(() => renderServiceWorker("const nothing = 1;", "one")).toThrow("no build id slot");
  });
});

describe("push notifications", () => {
  it("still show the message the server sent", async () => {
    const listeners: Record<string, Listener> = {};
    const showNotification = vi.fn(async () => undefined);
    const scope = {
      location: new URL(`${ORIGIN}/sw.js`),
      clients: {},
      registration: { showNotification },
      addEventListener: (type: string, listener: Listener) => {
        listeners[type] = listener;
      },
    };
    vm.runInContext(
      renderServiceWorker(SOURCE, PRODUCTION),
      vm.createContext({ self: scope, URL, caches: new FakeCaches() }),
    );
    const waits: Promise<unknown>[] = [];
    listeners.push!({
      data: {
        json: () => ({ title: "Dərs cədvəli dəyişdi", body: "1-301", tag: "t", url: "/schedule" }),
      },
      waitUntil: (promise: Promise<unknown>) => waits.push(promise),
    });
    await Promise.all(waits);
    expect(showNotification).toHaveBeenCalledWith(
      "Dərs cədvəli dəyişdi",
      expect.objectContaining({ body: "1-301", data: { url: "/schedule" } }),
    );
  });
});
