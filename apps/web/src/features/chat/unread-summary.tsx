import { MessagesSquare } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { CountBadge } from "@/components/ui/count-badge";
import { EmptyState } from "@/components/ui/empty-state";
import { TextLink } from "@/components/ui/text-link";

import type { Channel } from "./model";

const SHOWN = 5;

/** Dashboard widget (§6): the channels with unread messages, most unread first. */
export function UnreadSummary({ channels }: { channels: Channel[] }) {
  const t = useTranslations("dashboard");
  const unread = channels
    .filter((channel) => channel.unread_count > 0)
    .sort((a, b) => b.unread_count - a.unread_count)
    .slice(0, SHOWN);
  if (!unread.length) {
    return (
      <EmptyState
        className="py-0"
        icon={MessagesSquare}
        message={t("chatPlaceholder")}
        action={<TextLink href="/chat">{t("chatOpen")}</TextLink>}
      />
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col">
        {unread.map((channel) => (
          <li key={channel.id}>
            <Link
              href={`/chat/${channel.id}`}
              className="flex min-h-11 items-center gap-2 rounded-control px-2 hover:bg-bg-subtle lg:min-h-9"
            >
              <span className="min-w-0 flex-1 truncate">{channel.name}</span>
              <CountBadge count={channel.unread_count} />
            </Link>
          </li>
        ))}
      </ul>
      <TextLink href="/chat">{t("chatOpen")}</TextLink>
    </div>
  );
}
