import { CACHE_PREFIX, OFFLINE_DB, STORAGE_PREFIX } from "./policy";
import { deleteDatabase } from "./store";

const CHANNEL = "sa-offline";

/** Tabs of the same browser hear a wipe so they drop what they hold in memory (their writes are refused anyway). */
export function onWiped(listener: () => void): () => void {
  if (typeof BroadcastChannel === "undefined") return () => undefined;
  const channel = new BroadcastChannel(CHANNEL);
  channel.onmessage = () => listener();
  return () => channel.close();
}

async function deleteCaches(): Promise<void> {
  if (typeof caches === "undefined") return;
  const names = await caches.keys();
  await Promise.all(names.filter((n) => n.startsWith(CACHE_PREFIX)).map((n) => caches.delete(n)));
}

function clearStorageKeys(): void {
  const keys: string[] = [];
  for (let index = 0; index < localStorage.length; index += 1) {
    const key = localStorage.key(index);
    if (key?.startsWith(STORAGE_PREFIX)) keys.push(key);
  }
  keys.forEach((key) => localStorage.removeItem(key));
}

/**
 * Removes everything the offline feature keeps on this device: the IndexedDB database, the service worker's caches
 * and the small `localStorage` markers. Each step runs even if another fails; the result says whether all did.
 */
export async function wipeOfflineData(): Promise<boolean> {
  const steps = [deleteDatabase, deleteCaches, async () => clearStorageKeys()];
  const outcomes = await Promise.allSettled(steps.map((step) => step()));
  if (typeof BroadcastChannel !== "undefined") {
    const channel = new BroadcastChannel(CHANNEL);
    channel.postMessage("wiped");
    channel.close();
  }
  return outcomes.every((outcome) => outcome.status === "fulfilled");
}

/** Whether anything of the offline feature is on this device; asking does not create the database. */
export async function hasOfflineData(): Promise<boolean> {
  const databases = (await indexedDB.databases?.()) ?? [{ name: OFFLINE_DB }];
  if (databases.some((database) => database.name === OFFLINE_DB)) return true;
  return (
    typeof caches !== "undefined" && (await caches.keys()).some((n) => n.startsWith(CACHE_PREFIX))
  );
}
