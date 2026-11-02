import { deleteDB, openDB, type DBSchema, type IDBPDatabase } from "idb";

import { belongsTo, OFFLINE_DB, snapshotKey, type SnapshotKind } from "./policy";

/** The browser's single record of whose data is on the device and whether storing is switched on. */
export type DeviceRecord = {
  userId: string;
  /** The "Bu cihazda oflayn saxla" switch; off by default, per device (D-117). */
  enabled: boolean;
  /** Absolute end of the web session, epoch seconds (D-040); stored data is not shown after it. */
  sessionEndsAt: number;
};

export type Snapshot<T = unknown> = {
  key: string;
  userId: string;
  kind: SnapshotKind;
  savedAt: number;
  data: T;
};

interface OfflineSchema extends DBSchema {
  meta: { key: "device"; value: DeviceRecord };
  snapshots: { key: string; value: Snapshot; indexes: { "by-user": string } };
}

const VERSION = 1;
let opened: Promise<IDBPDatabase<OfflineSchema>> | null = null;

export function database(): Promise<IDBPDatabase<OfflineSchema>> {
  opened ??= openDB<OfflineSchema>(OFFLINE_DB, VERSION, {
    upgrade(db) {
      db.createObjectStore("meta");
      db.createObjectStore("snapshots", { keyPath: "key" }).createIndex("by-user", "userId");
    },
    // A wipe in another tab deletes the database; hold no connection that would block it.
    blocking(_current, _blocked, event) {
      (event.target as IDBDatabase).close();
      opened = null;
    },
    terminated() {
      opened = null;
    },
  });
  return opened;
}

export async function closeDatabase(): Promise<void> {
  const pending = opened;
  opened = null;
  if (pending) (await pending.catch(() => null))?.close();
}

export async function deleteDatabase(): Promise<void> {
  await closeDatabase();
  await deleteDB(OFFLINE_DB);
}

export async function readDevice(): Promise<DeviceRecord | null> {
  return (await (await database()).get("meta", "device")) ?? null;
}

/**
 * Registers the signed-in user as the owner of this device's offline data. Data of another account is deleted
 * first by the caller (`claimDevice` in `device.ts`); here the record is only written.
 */
export async function writeDevice(record: DeviceRecord): Promise<void> {
  await (await database()).put("meta", record, "device");
}

/**
 * Stores one snapshot, only while the device record names this user and has storing switched on. The check and the
 * write share one transaction, so a tab that was wiped (or whose user was replaced) can never write again.
 */
export async function putSnapshot<T>(
  userId: string,
  kind: SnapshotKind,
  id: string,
  data: T,
  now = Date.now(),
): Promise<boolean> {
  const db = await database();
  const tx = db.transaction(["meta", "snapshots"], "readwrite");
  const device = await tx.objectStore("meta").get("device");
  if (!device || device.userId !== userId || !device.enabled) {
    await tx.done;
    return false;
  }
  await tx.objectStore("snapshots").put({
    key: snapshotKey(userId, kind, id),
    userId,
    kind,
    savedAt: now,
    data,
  });
  await tx.done;
  return true;
}

export async function getSnapshot<T>(
  userId: string,
  kind: SnapshotKind,
  id = "",
): Promise<Snapshot<T> | null> {
  const found = await (await database()).get("snapshots", snapshotKey(userId, kind, id));
  // The key already carries the user id; the field is checked as well so a damaged record is never shown.
  return found && found.userId === userId && belongsTo(userId, found.key)
    ? (found as Snapshot<T>)
    : null;
}

export async function listSnapshots<T>(userId: string, kind: SnapshotKind): Promise<Snapshot<T>[]> {
  const all = await (await database()).getAllFromIndex("snapshots", "by-user", userId);
  return all.filter((entry) => entry.kind === kind) as Snapshot<T>[];
}

export async function deleteSnapshots(keys: string[]): Promise<void> {
  if (keys.length === 0) return;
  const tx = (await database()).transaction("snapshots", "readwrite");
  await Promise.all([...keys.map((key) => tx.store.delete(key)), tx.done]);
}

export async function clearSnapshots(): Promise<void> {
  await (await database()).clear("snapshots");
}
