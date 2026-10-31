"use client";

import { useEffect, useState } from "react";

import type { components } from "@/lib/api/schema";

export type AttendanceOffering = components["schemas"]["AttendanceOfferingOut"];
export type AttendanceSession = components["schemas"]["AttendanceSessionOut"];

export function formatRate(rate: number): string {
  return `${Math.round(rate * 100)} %`;
}

/** Below 60 % a student risks the course attendance limit; the tag always carries the number too. */
export function rateTone(
  rate: number,
  total: number,
): "neutral" | "success" | "warning" | "danger" {
  if (total === 0) return "neutral";
  if (rate >= 0.8) return "success";
  if (rate >= 0.6) return "warning";
  return "danger";
}

/** The current time in milliseconds, refreshed once a second; the clock is read in a callback, not in render. */
export function useNow(): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return now;
}
