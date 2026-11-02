import { useLocale } from "next-intl";

import type { Locale } from "@/i18n/config";

import {
  formatDate,
  formatDateTime,
  formatDateTimeRange,
  formatDayMonth,
  formatNumber,
  formatWeekdayDate,
} from "./format";

/** The date and number formatters bound to the language of the page, so a component never passes it around. */
export function useFormatters() {
  const locale = useLocale() as Locale;
  return {
    formatDate: (value: Date | string) => formatDate(value, locale),
    formatDateTime: (value: Date | string) => formatDateTime(value, locale),
    formatDateTimeRange: (start: string, end: string) => formatDateTimeRange(start, end, locale),
    formatDayMonth: (day: string) => formatDayMonth(day, locale),
    formatWeekdayDate: (day: string) => formatWeekdayDate(day, locale),
    formatNumber: (value: number) => formatNumber(value, locale),
  };
}
