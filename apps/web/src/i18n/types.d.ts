import type messages from "../../messages/az.json";

declare module "next-intl" {
  interface AppConfig {
    Locale: "az";
    Messages: typeof messages;
  }
}
