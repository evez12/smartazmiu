import { MessagesSquare } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { CountBadge } from "@/components/ui/count-badge";
import { EmptyState } from "@/components/ui/empty-state";
import { TextLink } from "@/components/ui/text-link";

import { badgeCounts, type Channel } from "./model";

const SHOWN = 5;

/** Dashboard widget (§6): the channels with unread messages, most unread first; muted ones are left out. */
export function UnreadSummary({ channels }: { channels: Channel[] }) {
  const t = useTranslations("dashboard");
  const unread = channels
    .map((channel) => ({ channel, counts: badgeCounts(channel) }))
    .filter(({ counts }) => counts.unread + counts.mentions > 0)
    .sort((a, b) => b.counts.mentions - a.counts.mentions || b.counts.unread - a.counts.unread)
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
        {unread.map(({ channel, counts }) => (
          <li key={channel.id}>
            <Link
              href={`/chat/${channel.id}`}
              className="flex min-h-11 items-center gap-2 rounded-control px-2 hover:bg-bg-subtle lg:min-h-9"
            >
              <span className="min-w-0 flex-1 truncate">{channel.name}</span>
              <CountBadge count={counts.mentions} kind="mention" />
              <CountBadge count={counts.unread} />
            </Link>
          </li>
        ))}
      </ul>
      <TextLink href="/chat">{t("chatOpen")}</TextLink>
    </div>
  );
}
