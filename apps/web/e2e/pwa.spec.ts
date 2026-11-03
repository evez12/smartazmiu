import { randomBytes } from "node:crypto";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Locator, type Page } from "@playwright/test";

import { hydrated, password, signIn, test } from "./support/auth";
import { undersizedTargets } from "./support/touch-targets";

test.skip(!password, "KEYCLOAK_TEST_USER_PASSWORD is not set");
// WebKit does not send the app's Secure state cookie back over plain http://localhost, so the sign-in callback
// ends in `signin_expired` and no test can reach a signed-in page. `make up-tls` gives it https (D-128, D-133).
test.skip(
  ({ browserName, baseURL }) => browserName === "webkit" && !baseURL?.startsWith("https:"),
  "WebKit cannot complete the sign-in over plain HTTP on localhost; use make up-tls (D-128)",
);
// In the WebKit build Playwright ships, `PushManager.getSubscription()` on an active worker blocks the page's main
// thread (a heartbeat inside the page stops), and the notification settings page and the chat menu call it on mount.
// The offline specs never use push, so WebKit gets an answer of "no subscription" (D-133).
test.beforeEach(async ({ context, browserName }) => {
  if (browserName !== "webkit") return;
  await context.addInitScript(() => {
    PushManager.prototype.getSubscription = () => Promise.resolve(null);
  });
});
const FIREFOX_OFFLINE =
  "Playwright's offline mode does not reach the service worker's own requests in Firefox (D-128)";
// The service worker registers only in a production build (the development server serves changing code under
// one address), so these specs need `make up` and `E2E_BASE_URL=http://localhost` (like the upload specs, D-068).
test.skip(
  !process.env.E2E_BASE_URL,
  "needs the production build: make up, E2E_BASE_URL=http://localhost",
);

/*
 * Sprint 15, Group B (D-117, D-118): the app installs, shows the schedule and the newest channel messages without
 * a connection, and removes everything it stored when the session ends. A seeded student only signs in and writes
 * a marked message, which the test removes (D-040, D-065).
 */
const AYSEL = { username: "aysel.mammadova", email: "aysel.mammadova@smartazmiu.test" };
const DB = "smartazmiu-offline";

type OfflineDb = {
  device: { userId: string; enabled: boolean; sessionEndsAt: number } | null;
  snapshots: { key: string; kind: string; savedAt: number }[];
} | null;

/** What this browser holds for the offline feature; null when the database does not exist. */
async function offlineDb(page: Page): Promise<OfflineDb> {
  return page.evaluate(async (name) => {
    const known = (await indexedDB.databases()).some((database) => database.name === name);
    if (!known) return null;
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      const request = indexedDB.open(name);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    const all = <T>(store: string) =>
      new Promise<T[]>((resolve, reject) => {
        const request = db.transaction(store).objectStore(store).getAll();
        request.onsuccess = () => resolve(request.result as T[]);
        request.onerror = () => reject(request.error);
      });
    const [devices, snapshots] = await Promise.all([
      all<{ userId: string; enabled: boolean; sessionEndsAt: number }>("meta"),
      all<{ key: string; kind: string; savedAt: number }>("snapshots"),
    ]);
    db.close();
    return { device: devices[0] ?? null, snapshots };
  }, DB);
}

async function cacheNames(page: Page): Promise<string[]> {
  return page.evaluate(async () => (await caches.keys()).filter((name) => name.startsWith("sa-")));
}

/** Every address held in the worker's caches, with the cache it is in. */
async function cachedUrls(page: Page): Promise<{ cache: string; path: string }[]> {
  return page.evaluate(async () => {
    const found: { cache: string; path: string }[] = [];
    for (const name of (await caches.keys()).filter((n) => n.startsWith("sa-"))) {
      for (const request of await (await caches.open(name)).keys()) {
        found.push({ cache: name, path: new URL(request.url).pathname });
      }
    }
    return found;
  });
}

/**
 * After a wipe the offline page and everything of the user are gone. Static files the sign-in page loads next are
 * kept again by the worker (public, the same for everyone), so the check is what may be in the caches, not that
 * they are empty.
 */
async function expectOnlyPublicFilesCached(page: Page) {
  const urls = await cachedUrls(page);
  expect(urls.filter((entry) => entry.cache.startsWith("sa-shell-"))).toEqual([]);
  expect(
    urls.filter((entry) => !/^\/(_next\/static\/|icons\/|icon\.svg)/.test(entry.path)),
  ).toEqual([]);
}

async function offlineMarkers(page: Page): Promise<string[]> {
  return page.evaluate(() =>
    Object.keys(localStorage).filter((key) => key.startsWith("sa:offline:")),
  );
}

function sidebar(page: Page): Locator {
  return page.getByRole("navigation", { name: "Kanallar" });
}

function messageLog(page: Page): Locator {
  return page.getByRole("log", { name: /kanalının mesajları$/ });
}

async function online(page: Page) {
  await expect(sidebar(page).getByRole("status")).toHaveCount(0, { timeout: 15_000 });
}

async function send(page: Page, text: string) {
  const field = page.getByRole("combobox", { name: "Mesaj" });
  await field.fill(text);
  await field.press("Enter");
}

/** Opens the first course channel in the chat and returns its name. */
async function openFirstCourse(page: Page): Promise<string> {
  const course = sidebar(page)
    .getByRole("region", { name: "Fənlər" })
    .locator("> ul")
    .getByRole("link")
    .first();
  const name = (await course.locator("span.truncate").first().innerText()).trim();
  await course.click();
  await expect(page.getByRole("heading", { level: 2, name })).toBeVisible();
  await online(page);
  return name;
}

async function expectNoSeriousViolations(page: Page, where: string) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(
    violations
      .filter((v) => v.impact === "serious" || v.impact === "critical")
      .map((v) => `${v.id}: ${v.nodes.length}`),
    where,
  ).toEqual([]);
}

/** Turns "Bu cihazda oflayn saxla" on and waits until the first download and the offline page are stored. */
async function enableOfflineStorage(page: Page) {
  await page.goto("/notifications/settings");
  await hydrated(page);
  const toggle = page.getByRole("switch", { name: "Bu cihazda oflayn saxla" });
  await expect(toggle).not.toBeChecked();
  await toggle.click();
  await expect(toggle).toBeChecked();
  await expect(page.getByText(/^Son yenilənmə: /)).toBeVisible({ timeout: 30_000 });
  await expect
    .poll(async () => (await cacheNames(page)).some((name) => name.startsWith("sa-shell-")), {
      timeout: 30_000,
    })
    .toBe(true);
}

async function weekClasses(page: Page): Promise<string[]> {
  return page.locator('section[aria-labelledby="schedule-week"] li .font-medium').allInnerTexts();
}

test("the app can be installed: manifest, icons, worker script and no installability error", async ({
  page,
  request,
  browserName,
}) => {
  await signIn(page, AYSEL.username, "/");
  await expect(page.locator('link[rel="manifest"]')).toHaveAttribute(
    "href",
    "/manifest.webmanifest",
  );
  await expect(page.locator('link[rel="apple-touch-icon"]')).toHaveCount(1);

  const manifest = await (await request.get("/manifest.webmanifest")).json();
  expect(manifest).toMatchObject({
    name: "SmartAzMİU",
    display: "standalone",
    start_url: "/",
    lang: "az",
  });
  for (const icon of manifest.icons as { src: string; type: string }[]) {
    const response = await request.get(icon.src);
    expect(response.status(), icon.src).toBe(200);
    expect(response.headers()["content-type"]).toBe(icon.type);
  }
  expect(
    (manifest.icons as { purpose: string }[]).some((icon) => icon.purpose === "maskable"),
  ).toBe(true);
  const russian = await (
    await request.get("/manifest.webmanifest", { headers: { Cookie: "NEXT_LOCALE=ru" } })
  ).json();
  expect(russian.lang).toBe("ru");
  expect(russian.description).not.toBe(manifest.description);

  const script = await request.get("/sw.js");
  expect(script.headers()["cache-control"]).toContain("no-cache");
  expect(await script.text()).not.toContain("__BUILD_ID__");

  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload();
  await hydrated(page);
  expect(await page.evaluate(() => navigator.serviceWorker.controller !== null)).toBe(true);

  // Chrome's own installability check (what Lighthouse reports as "installable"); a Chromium-only protocol.
  test.skip(
    browserName !== "chromium",
    "The installability check uses the Chrome DevTools protocol",
  );
  const client = await page.context().newCDPSession(page);
  const { installabilityErrors } = await client.send("Page.getInstallabilityErrors");
  expect(installabilityErrors).toEqual([]);
});

test("the schedule and the newest channel messages stay readable offline, and coming back refreshes them", async ({
  page,
  records,
}) => {
  test.skip(test.info().project.name === "pwa-firefox", FIREFOX_OFFLINE);
  test.setTimeout(240_000);
  const marker = records.chatMessages(randomBytes(6).toString("hex"), [AYSEL.email]);
  await signIn(page, AYSEL.username, "/chat");
  await online(page);
  const courseName = await openFirstCourse(page);
  await send(page, `Oflayn yoxlama üçün mesaj. ${marker}`);
  await expect(messageLog(page).getByText(marker)).toBeVisible();

  await page.goto("/schedule");
  await hydrated(page);
  const onlineClasses = await weekClasses(page);
  expect(onlineClasses.length).toBeGreaterThan(0);

  // Nothing is stored until the user switches it on.
  expect((await offlineDb(page))?.snapshots ?? []).toEqual([]);
  await enableOfflineStorage(page);
  const stored = (await offlineDb(page))!;
  expect(stored.device).toMatchObject({ enabled: true });
  expect(stored.snapshots.map((snapshot) => snapshot.kind)).toEqual(
    expect.arrayContaining(["schedule", "channels", "channel"]),
  );
  // Every key belongs to the signed-in user.
  expect(new Set(stored.snapshots.map((snapshot) => snapshot.key.split(":")[1]))).toEqual(
    new Set([stored.device!.userId]),
  );
  const savedBefore = stored.snapshots.find((snapshot) => snapshot.kind === "schedule")!.savedAt;

  await page.context().setOffline(true);
  await page.goto("/schedule");
  await hydrated(page);
  await expect(page.getByRole("heading", { level: 1, name: "Oflayn rejim" })).toBeVisible();
  await expect(page.getByText("İnternet bağlantısı yoxdur")).toBeVisible();
  await expect(page.getByText(/^Son yenilənmə: /)).toBeVisible();
  expect(await weekClasses(page)).toEqual(onlineClasses);

  await page.getByRole("tab", { name: "Kanallar" }).click();
  await page
    .getByRole("button", { name: new RegExp(courseName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) })
    .first()
    .click();
  await expect(page.getByText(marker)).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);

  // Quality of the offline page in both themes (a phone is checked in its own test below).
  for (const scheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await expectNoSeriousViolations(page, `offline page, ${scheme}`);
  }

  await page.context().setOffline(false);
  await expect(page.getByText("Bağlantı bərpa olundu")).toBeVisible();
  await page.getByRole("link", { name: "Tətbiqə qayıdın" }).click();
  await hydrated(page);
  // Back online the stored copy is refreshed without anything being done.
  await expect
    .poll(
      async () =>
        (await offlineDb(page))?.snapshots.find((snapshot) => snapshot.kind === "schedule")
          ?.savedAt ?? 0,
      { timeout: 30_000 },
    )
    .toBeGreaterThan(savedBefore);
});

test("signing out deletes Cache Storage and IndexedDB", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page, AYSEL.username, "/");
  await enableOfflineStorage(page);
  expect(await offlineDb(page)).not.toBeNull();
  expect((await cacheNames(page)).length).toBeGreaterThan(0);

  await page.getByRole("button", { name: /Profil menyusu/ }).click();
  await page.getByRole("menuitem", { name: "Çıxış edin" }).click();
  await expect(page).toHaveURL(/\/login\?status=signed_out/);

  await expect.poll(() => offlineDb(page), { timeout: 15_000 }).toBeNull();
  await expectOnlyPublicFilesCached(page);
  expect(await offlineMarkers(page)).toEqual([]);
});

test("a session that ended without signing out is cleaned at the sign-in page, and the next user starts with nothing", async ({
  page,
  accounts,
}) => {
  test.skip(test.info().project.name === "pwa-firefox", FIREFOX_OFFLINE);
  test.setTimeout(180_000);
  await signIn(page, AYSEL.username, "/");
  await enableOfflineStorage(page);
  const aysel = (await offlineDb(page))!.device!.userId;

  // The session ends on the server's side (expiry, revocation): the cookies are gone, the device is not told.
  await page.context().clearCookies();
  await page.goto("/login");
  await expect.poll(() => offlineDb(page), { timeout: 15_000 }).toBeNull();
  await expectOnlyPublicFilesCached(page);

  const student = await accounts.create("student", { givenName: "Nərmin", familyName: "Şükürova" });
  await signIn(page, student, "/notifications/settings");
  await expect(page.getByRole("switch", { name: "Bu cihazda oflayn saxla" })).not.toBeChecked();
  const device = await offlineDb(page);
  expect(device?.device?.userId).not.toBe(aysel);
  expect(device?.device?.enabled).toBe(false);
  expect(device?.snapshots).toEqual([]);

  // The offline page is stored again for the new user a moment after signing in.
  await expect
    .poll(async () => (await cachedUrls(page)).some((entry) => entry.path === "/offline"), {
      timeout: 30_000,
    })
    .toBe(true);
  await page.context().setOffline(true);
  await page.goto("/schedule");
  await hydrated(page);
  await expect(page.getByText(/Oflayn saxlama bu cihazda aktiv deyil/)).toBeVisible();
  await page.context().setOffline(false);
});

test("signing out without a connection deletes the data at once and ends the session when it returns", async ({
  page,
}) => {
  test.skip(test.info().project.name === "pwa-firefox", FIREFOX_OFFLINE);
  test.setTimeout(180_000);
  await signIn(page, AYSEL.username, "/");
  await enableOfflineStorage(page);

  await page.context().setOffline(true);
  await page.goto("/schedule");
  await hydrated(page);
  await page.getByRole("button", { name: "Çıxış edin" }).click();
  await expect(page.getByText(/Bu cihazdan çıxış etdiniz/)).toBeVisible();
  expect(await offlineDb(page)).toBeNull();
  expect(await cacheNames(page)).toEqual([]);

  await page.context().setOffline(false);
  await page.goto("/");
  await expect(page).toHaveURL(/\/login\?status=signed_out/, { timeout: 30_000 });
  // The server session is really over: the app no longer opens.
  await page.goto("/schedule");
  await expect(page).toHaveURL(/\/login\?returnTo=/);
});

test("a new version waits for the user, and the page is not reloaded over unsent text", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page, AYSEL.username, "/chat");
  await online(page);
  await openFirstCourse(page);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload();
  await hydrated(page);
  expect(await page.evaluate(() => navigator.serviceWorker.controller !== null)).toBe(true);

  // A worker script at another address in the same scope stands in for the next deploy.
  await page.evaluate(() =>
    navigator.serviceWorker.register("/sw.js?next=1", { updateViaCache: "none" }),
  );
  const banner = page.getByRole("status").filter({ hasText: "Yeni versiya var" });
  await expect(banner).toBeVisible({ timeout: 30_000 });
  await expectNoSeriousViolations(page, "update banner");

  const field = page.getByRole("combobox", { name: "Mesaj" });
  await field.fill("Göndərilməmiş mətn");
  const update = banner.getByRole("button", { name: "Yeniləyin" });
  await expect(update).toBeDisabled();
  await expect(banner).toContainText("Göndərilməmiş mətniniz");
  expect(await page.evaluate(() => navigator.serviceWorker.controller?.scriptURL)).not.toContain(
    "next=1",
  );

  await field.fill("");
  await expect(update).toBeEnabled();
  const loaded = page.waitForEvent("load");
  await update.click();
  await loaded;
  await hydrated(page);
  expect(await page.evaluate(() => navigator.serviceWorker.controller?.scriptURL)).toContain(
    "next=1",
  );
});

test("the install offer comes from the second visit and stays away once dismissed", async ({
  page,
}) => {
  await signIn(page, AYSEL.username, "/");
  const offer = () =>
    page.evaluate(() => {
      const event = new Event("beforeinstallprompt", { cancelable: true });
      Object.assign(event, { prompt: () => Promise.resolve() });
      window.dispatchEvent(event);
    });
  const banner = page
    .getByRole("status")
    .filter({ hasText: "SmartAzMİU-nu cihazınıza quraşdırın" });

  // A new browser session starts here: the visit counter, not the sign-in, decides.
  await page.evaluate(() => {
    localStorage.removeItem("sa:install:visits");
    localStorage.removeItem("sa:install:dismissed");
    sessionStorage.clear();
  });
  await page.reload();
  await hydrated(page);
  await offer();
  await expect(banner).toHaveCount(0);

  await page.evaluate(() => sessionStorage.clear());
  await page.reload();
  await hydrated(page);
  await offer();
  await expect(banner).toBeVisible();
  await expectNoSeriousViolations(page, "install offer");

  await banner.getByRole("button", { name: "Bağlayın" }).click();
  await expect(banner).toHaveCount(0);
  await page.evaluate(() => sessionStorage.clear());
  await page.reload();
  await hydrated(page);
  await offer();
  await expect(banner).toHaveCount(0);
});

test("a message written offline is delivered once when the connection returns, with the worker active", async ({
  page,
  records,
}) => {
  test.setTimeout(180_000);
  const marker = records.chatMessages(randomBytes(6).toString("hex"), [AYSEL.email]);
  await signIn(page, AYSEL.username, "/chat");
  await online(page);
  await openFirstCourse(page);
  await page.evaluate(() => navigator.serviceWorker.ready);

  await page.context().setOffline(true);
  await expect(page.getByText("İnternet bağlantısı yoxdur")).toBeVisible();
  await send(page, `Bağlantı yox idi, bunu sonra göndərin. ${marker}`);
  await expect(messageLog(page).getByText("Bağlantı bərpa olunanda göndəriləcək")).toBeVisible();
  await page.context().setOffline(false);

  await expect(messageLog(page).getByText(marker)).toHaveCount(1, { timeout: 30_000 });
  await expect(messageLog(page).getByText("Bağlantı bərpa olunanda göndəriləcək")).toHaveCount(0);
  await expect(page.getByText("İnternet bağlantısı yoxdur")).toHaveCount(0);
  await page.reload();
  await hydrated(page);
  await expect(messageLog(page).getByText(marker)).toHaveCount(1);
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 320, height: 640 }, hasTouch: true, isMobile: true });

  test("the offline switch, the offline page and the install offer fit 320 px with 44 px targets", async ({
    page,
  }) => {
    test.skip(test.info().project.name === "pwa-firefox", FIREFOX_OFFLINE);
    test.setTimeout(180_000);
    await signIn(page, AYSEL.username, "/");
    await enableOfflineStorage(page);
    expect(await undersizedTargets(page), "settings").toEqual([]);

    await page.evaluate(() => {
      localStorage.setItem("sa:install:visits", "1");
      localStorage.removeItem("sa:install:dismissed");
      sessionStorage.clear();
    });
    await page.goto("/");
    await hydrated(page);
    await page.evaluate(() => {
      const event = new Event("beforeinstallprompt", { cancelable: true });
      Object.assign(event, { prompt: () => Promise.resolve() });
      window.dispatchEvent(event);
    });
    const offer = page
      .getByRole("status")
      .filter({ hasText: "SmartAzMİU-nu cihazınıza quraşdırın" });
    await expect(offer).toBeVisible();
    expect(await undersizedTargets(page), "install offer").toEqual([]);

    await page.context().setOffline(true);
    await expect(page.getByText("İnternet bağlantısı yoxdur")).toBeVisible();
    expect(await undersizedTargets(page), "connection banner").toEqual([]);

    await page.goto("/schedule");
    await hydrated(page);
    await expect(page.getByRole("heading", { level: 1, name: "Oflayn rejim" })).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    expect(await undersizedTargets(page), "offline schedule").toEqual([]);
    await page.getByRole("tab", { name: "Kanallar" }).click();
    expect(await undersizedTargets(page), "offline channels").toEqual([]);
    await page
      .getByRole("list", { name: "Saxlanmış kanallar" })
      .getByRole("button")
      .first()
      .click();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    expect(await undersizedTargets(page), "offline history").toEqual([]);
    await page.context().setOffline(false);
  });
});
