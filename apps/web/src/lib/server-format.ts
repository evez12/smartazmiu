import "server-only";

import { getLocale } from "next-intl/server";

import type { Locale } from "@/i18n/config";

import {
  formatDate,
  formatDateTime,
  formatDateTimeRange,
  formatDayMonth,
  formatNumber,
  formatWeekdayDate,
} from "./format";

/** The same bound formatters as `useFormatters`, for async server components that cannot call hooks. */
export async function getFormatters() {
  const locale = (await getLocale()) as Locale;
  return {
    formatDate: (value: Date | string) => formatDate(value, locale),
    formatDateTime: (value: Date | string) => formatDateTime(value, locale),
    formatDateTimeRange: (start: string, end: string) => formatDateTimeRange(start, end, locale),
    formatDayMonth: (day: string) => formatDayMonth(day, locale),
    formatWeekdayDate: (day: string) => formatWeekdayDate(day, locale),
    formatNumber: (value: number) => formatNumber(value, locale),
  };
}
