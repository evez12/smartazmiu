"use client";

import { CircleAlert, FileText, X } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/cn";

import { useAttachmentErrorText } from "./message-attachments";
import { formatSize, type Upload } from "./uploads";

/** Files picked in the composer, with progress and failure states (§12.7). */
export function AttachmentChips({
  items,
  onRemove,
}: {
  items: Upload[];
  onRemove: (key: string) => void;
}) {
  const t = useTranslations("chat.attachments");
  const errorText = useAttachmentErrorText();
  return (
    <ul aria-label={t("picked")} className="flex flex-wrap gap-2">
      {items.map((item) => {
        const failed = item.state === "failed";
        return (
          <li
            key={item.key}
            className={cn(
              "flex max-w-full min-w-0 items-start gap-2 rounded-control border px-2 py-1.5 text-sm sm:max-w-72",
              failed ? "border-danger" : "border-border",
            )}
          >
            <Icon
              icon={failed ? CircleAlert : FileText}
              className={cn("mt-0.5 shrink-0", failed ? "text-danger" : "text-muted")}
            />
            <span className="flex min-w-0 flex-1 flex-col gap-1">
              <span className="truncate" title={item.file.name}>
                {item.file.name}
              </span>
              {item.state === "uploading" ? (
                <span
                  role="progressbar"
                  aria-label={t("uploading", { name: item.file.name })}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(item.progress * 100)}
                  className="block h-1 w-full overflow-hidden rounded-control bg-bg-subtle"
                >
                  <span
                    className="block h-full bg-primary transition-[width] duration-150"
                    style={{ width: `${Math.round(item.progress * 100)}%` }}
                  />
                </span>
              ) : (
                <span className={cn("text-xs", failed ? "text-danger" : "text-muted")}>
                  {failed ? errorText(item.error) : `${formatSize(item.file.size)} · ${t("ready")}`}
                </span>
              )}
            </span>
            <Button
              type="button"
              variant="tertiary"
              size="icon-dense"
              aria-label={t("remove", { name: item.file.name })}
              onClick={() => onRemove(item.key)}
            >
              <Icon icon={X} />
            </Button>
          </li>
        );
      })}
    </ul>
  );
}
