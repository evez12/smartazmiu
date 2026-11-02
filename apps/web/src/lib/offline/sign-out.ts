import { SIGN_OUT_PENDING_KEY } from "./policy";
import { wipeOfflineData } from "./wipe";

const CHANGED = "sa:signout-pending-changed";

export function isSignOutPending(): boolean {
  try {
    return localStorage.getItem(SIGN_OUT_PENDING_KEY) !== null;
  } catch {
    return false;
  }
}

export function clearSignOutPending(): void {
  try {
    localStorage.removeItem(SIGN_OUT_PENDING_KEY);
  } catch {
    // Storage blocked: there was nothing to clear.
  }
  window.dispatchEvent(new Event(CHANGED));
}

export function subscribeSignOutPending(onChange: () => void): () => void {
  window.addEventListener(CHANGED, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(CHANGED, onChange);
    window.removeEventListener("storage", onChange);
  };
}

/** Posts the same form the sign-out button posts, so the server session ends exactly as it does online. */
export function submitSignOut(csrfToken: string): void {
  const form = document.createElement("form");
  form.method = "post";
  form.action = "/auth/signout";
  form.hidden = true;
  const field = document.createElement("input");
  field.type = "hidden";
  field.name = "csrf";
  field.value = csrfToken;
  form.append(field);
  document.body.append(form);
  form.submit();
}

/**
 * The device side of signing out: the offline data goes first, before anything can fail. Returns true when the
 * server call can follow now; offline it is remembered and sent when the connection returns (D-117), because the
 * server session can only be ended by the server.
 */
export async function leaveDevice(online = navigator.onLine): Promise<boolean> {
  await wipeOfflineData();
  if (online) return true;
  localStorage.setItem(SIGN_OUT_PENDING_KEY, String(Date.now()));
  window.dispatchEvent(new Event(CHANGED));
  return false;
}
