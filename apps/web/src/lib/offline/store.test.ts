import "fake-indexeddb/auto";

import { IDBFactory } from "fake-indexeddb";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { claimDevice, setOfflineEnabled, wipeIfSessionEnded } from "./device";
import { SIGN_OUT_PENDING_KEY, STORAGE_PREFIX } from "./policy";
import { leaveDevice } from "./sign-out";
import {
  closeDatabase,
  getSnapshot,
  listSnapshots,
  putSnapshot,
  readDevice,
  writeDevice,
} from "./store";
import { hasOfflineData, wipeOfflineData } from "./wipe";

const AYSEL = "01a19d28-c354-7be3-83ff-a11dbd4de9d1";
const RAMIN = "01a19d28-c354-7be3-83ff-a11dbd4de9d2";
const IN_AN_HOUR = Math.floor(Date.now() / 1000) + 3600;

/** A Cache Storage that remembers names only; the worker's own caches are what a wipe has to remove. */
function fakeCaches(names: string[]) {
  const open = new Set(names);
  Object.defineProperty(globalThis, "caches", {
    configurable: true,
    value: {
      keys: async () => [...open],
      delete: async (name: string) => open.delete(name),
    },
  });
  return open;
}

beforeEach(() => {
  globalThis.indexedDB = new IDBFactory();
  localStorage.clear();
});

afterEach(async () => {
  await closeDatabase();
  Reflect.deleteProperty(globalThis, "caches");
});

describe("storing snapshots", () => {
  it("is refused until the device names the user and storing is switched on", async () => {
    expect(await putSnapshot(AYSEL, "schedule", "", { days: [] })).toBe(false);

    await claimDevice(AYSEL, IN_AN_HOUR);
    expect(await putSnapshot(AYSEL, "schedule", "", { days: [] })).toBe(false);

    await setOfflineEnabled(AYSEL, true, IN_AN_HOUR);
    expect(await putSnapshot(AYSEL, "schedule", "", { days: [] })).toBe(true);
    expect((await getSnapshot(AYSEL, "schedule"))?.data).toEqual({ days: [] });
  });

  it("is refused for a user other than the owner of the device", async () => {
    await claimDevice(AYSEL, IN_AN_HOUR);
    await setOfflineEnabled(AYSEL, true, IN_AN_HOUR);
    expect(await putSnapshot(RAMIN, "schedule", "", { days: [] })).toBe(false);
    expect(await getSnapshot(RAMIN, "schedule")).toBeNull();
  });

  it("keeps each user's snapshots apart in listings and reads", async () => {
    await claimDevice(AYSEL, IN_AN_HOUR);
    await setOfflineEnabled(AYSEL, true, IN_AN_HOUR);
    await putSnapshot(AYSEL, "channel", "c1", { id: "c1" });
    await putSnapshot(AYSEL, "channel", "c2", { id: "c2" });
    expect(await listSnapshots(AYSEL, "channel")).toHaveLength(2);
    expect(await listSnapshots(RAMIN, "channel")).toHaveLength(0);
    expect(await getSnapshot(RAMIN, "channel", "c1")).toBeNull();
  });

  it("stops after a wipe, even for a tab that still believes it owns the device", async () => {
    await claimDevice(AYSEL, IN_AN_HOUR);
    await setOfflineEnabled(AYSEL, true, IN_AN_HOUR);
    await wipeOfflineData();
    expect(await putSnapshot(AYSEL, "schedule", "", { days: [] })).toBe(false);
  });
});

describe("the owner of the device", () => {
  it("is replaced, with everything of the first user deleted, when someone else signs in", async () => {
    await claimDevice(AYSEL, IN_AN_HOUR);
    await setOfflineEnabled(AYSEL, true, IN_AN_HOUR);
    await putSnapshot(AYSEL, "channel", "c1", { id: "c1" });

    const record = await claimDevice(RAMIN, IN_AN_HOUR);

    expect(record).toEqual({ userId: RAMIN, enabled: false, sessionEndsAt: IN_AN_HOUR });
    expect(await getSnapshot(AYSEL, "channel", "c1")).toBeNull();
    expect(await listSnapshots(RAMIN, "channel")).toHaveLength(0);
  });

  it("keeps the switch when the same user signs in again, and moves the session end", async () => {
    await claimDevice(AYSEL, IN_AN_HOUR);
    await setOfflineEnabled(AYSEL, true, IN_AN_HOUR);
    const later = IN_AN_HOUR + 600;
    expect(await claimDevice(AYSEL, later)).toEqual({
      userId: AYSEL,
      enabled: true,
      sessionEndsAt: later,
    });
  });

  it("loses its stored data at once when the switch is turned off", async () => {
    await claimDevice(AYSEL, IN_AN_HOUR);
    await setOfflineEnabled(AYSEL, true, IN_AN_HOUR);
    await putSnapshot(AYSEL, "schedule", "", { days: [] });
    await setOfflineEnabled(AYSEL, false, IN_AN_HOUR);
    expect(await getSnapshot(AYSEL, "schedule")).toBeNull();
    expect((await readDevice())?.enabled).toBe(false);
  });
});

describe("the end of the session", () => {
  it("wipes everything once the absolute end has passed, without asking the server", async () => {
    await writeDevice({ userId: AYSEL, enabled: true, sessionEndsAt: 1_000 });
    expect(await wipeIfSessionEnded(999_000)).toBe(false);
    expect(await wipeIfSessionEnded(1_000_000)).toBe(true);
    expect(await readDevice()).toBeNull();
  });

  it("does nothing when there is no device record", async () => {
    expect(await wipeIfSessionEnded()).toBe(false);
  });
});

describe("wiping", () => {
  it("deletes the database, the worker's caches and the offline markers, and nothing else", async () => {
    const caches = fakeCaches(["sa-shell-b1", "sa-static-b1", "other-app-cache"]);
    localStorage.setItem(`${STORAGE_PREFIX}shell`, "b1:az");
    localStorage.setItem("sa:install:dismissed", "1");
    await claimDevice(AYSEL, IN_AN_HOUR);

    expect(await wipeOfflineData()).toBe(true);

    expect(await readDevice()).toBeNull();
    expect([...caches]).toEqual(["other-app-cache"]);
    expect(localStorage.getItem(`${STORAGE_PREFIX}shell`)).toBeNull();
    expect(localStorage.getItem("sa:install:dismissed")).toBe("1");
  });

  it("reports whether anything of the feature is on the device", async () => {
    fakeCaches([]);
    expect(await hasOfflineData()).toBe(false);
    await claimDevice(AYSEL, IN_AN_HOUR);
    expect(await hasOfflineData()).toBe(true);
    await wipeOfflineData();
    expect(await hasOfflineData()).toBe(false);
    fakeCaches(["sa-shell-b1"]);
    expect(await hasOfflineData()).toBe(true);
  });
});

describe("signing out on the device", () => {
  it("wipes first and lets the server call follow when online", async () => {
    fakeCaches(["sa-static-b1"]);
    await claimDevice(AYSEL, IN_AN_HOUR);
    expect(await leaveDevice(true)).toBe(true);
    expect(await readDevice()).toBeNull();
    expect(localStorage.getItem(SIGN_OUT_PENDING_KEY)).toBeNull();
  });

  it("wipes and remembers the server call when offline, and the marker survives later wipes", async () => {
    fakeCaches([]);
    await claimDevice(AYSEL, IN_AN_HOUR);
    expect(await leaveDevice(false)).toBe(false);
    expect(await readDevice()).toBeNull();
    expect(localStorage.getItem(SIGN_OUT_PENDING_KEY)).not.toBeNull();
    await wipeOfflineData();
    expect(localStorage.getItem(SIGN_OUT_PENDING_KEY)).not.toBeNull();
  });
});
