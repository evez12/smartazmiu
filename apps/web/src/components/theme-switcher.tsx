"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { ToggleGroup } from "radix-ui";
import { useSyncExternalStore } from "react";

import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/cn";

const options = [
  { value: "light", icon: Sun },
  { value: "dark", icon: Moon },
  { value: "system", icon: Monitor },
] as const;

const subscribeNoop = () => () => {};

/** Light / dark / system choice. The stored theme is only known in the browser, so the server renders none selected. */
export function ThemeSwitcher({ className }: { className?: string }) {
  const t = useTranslations("theme");
  const { theme, setTheme } = useTheme();
  const hydrated = useSyncExternalStore(
    subscribeNoop,
    () => true,
    () => false,
  );

  return (
    <ToggleGroup.Root
      type="single"
      aria-label={t("label")}
      value={hydrated ? (theme ?? "system") : ""}
      onValueChange={(value) => {
        if (value) setTheme(value);
      }}
      className={cn(
        "inline-flex rounded-control border border-border-control bg-surface p-0.5",
        className,
      )}
    >
      {options.map((option) => (
        <ToggleGroup.Item
          key={option.value}
          value={option.value}
          className={cn(
            "inline-flex h-7 items-center gap-1.5 rounded-[2px] px-2 text-sm text-muted transition-colors",
            "hover:text-text data-[state=on]:bg-primary data-[state=on]:text-primary-contrast",
            "pointer-coarse:h-10",
          )}
        >
          <Icon icon={option.icon} />
          <span className="max-sm:sr-only">{t(option.value)}</span>
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}
