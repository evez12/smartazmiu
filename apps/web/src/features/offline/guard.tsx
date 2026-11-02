"use client";

import { useEffect } from "react";

import { clearSignOutPending } from "@/lib/offline/sign-out";
import { hasOfflineData, wipeOfflineData } from "@/lib/offline/wipe";

/**
 * Rendered on the sign-in page. A page without a session means the previous session is over (sign-out, expiry,
 * revocation), so whatever the offline feature still holds on this device is deleted before anyone signs in (D-117).
 */
export function OfflineGuard() {
  useEffect(() => {
    clearSignOutPending();
    void hasOfflineData()
      .then((present) => (present ? wipeOfflineData() : undefined))
      .catch(() => undefined);
  }, []);
  return null;
}
