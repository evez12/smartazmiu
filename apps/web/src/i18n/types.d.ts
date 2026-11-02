import type messages from "../../messages/az.json";

declare module "next-intl" {
  interface AppConfig {
    Locale: "az" | "en" | "ru";
    Messages: typeof messages;
  }
}
