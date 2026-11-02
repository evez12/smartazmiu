/** Fired in the tab that changed the device record (the switch), so the runtime reads it again. */
export const DEVICE_CHANGED = "sa:offline-device-changed";

export function notifyDeviceChanged(): void {
  window.dispatchEvent(new Event(DEVICE_CHANGED));
}
