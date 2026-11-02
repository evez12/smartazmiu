import { clearSnapshots, getSnapshot, readDevice, writeDevice, type DeviceRecord } from "./store";
import { wipeOfflineData } from "./wipe";

/**
 * Makes the signed-in user the owner of this device's offline data. If the data belongs to someone else it is
 * deleted first, so a second person on the same browser starts with nothing of the first (§14, D-117).
 */
export async function claimDevice(userId: string, sessionEndsAt: number): Promise<DeviceRecord> {
  const current = await readDevice();
  if (current && current.userId !== userId) await wipeOfflineData();
  const record: DeviceRecord =
    current && current.userId === userId
      ? { ...current, sessionEndsAt }
      : { userId, enabled: false, sessionEndsAt };
  await writeDevice(record);
  return record;
}

/** Turns storing on or off for this device. Turning it off deletes the stored data at once. */
export async function setOfflineEnabled(
  userId: string,
  enabled: boolean,
  sessionEndsAt: number,
): Promise<DeviceRecord> {
  const device = await claimDevice(userId, sessionEndsAt);
  if (!enabled) await clearSnapshots();
  const record = { ...device, enabled };
  await writeDevice(record);
  return record;
}

/**
 * Offline data is usable only until the web session's absolute end (D-040), also when the device cannot reach the
 * server to find out. Returns true when the session had ended and everything was wiped.
 */
export async function wipeIfSessionEnded(nowMs = Date.now()): Promise<boolean> {
  const device = await readDevice();
  if (!device || device.sessionEndsAt * 1000 > nowMs) return false;
  await wipeOfflineData();
  return true;
}

/** When the schedule was last stored for the owner of this device, or null if nothing is stored. */
export async function lastSavedAt(): Promise<number | null> {
  const device = await readDevice();
  if (!device?.enabled) return null;
  return (await getSnapshot(device.userId, "schedule"))?.savedAt ?? null;
}
