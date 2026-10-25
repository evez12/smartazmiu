import { getRequestConfig } from "next-intl/server";

import messages from "../../messages/az.json";
import { DEFAULT_LOCALE, TIME_ZONE } from "./config";

// Azerbaijani is the only UI language until EN/RU arrive in Sprint 15; the locale is then read from a cookie.
export default getRequestConfig(async () => ({
  locale: DEFAULT_LOCALE,
  messages,
  timeZone: TIME_ZONE,
}));
