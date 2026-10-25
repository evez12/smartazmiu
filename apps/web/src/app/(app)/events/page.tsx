import { CalendarDays, Plus, Ticket } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { TextLink } from "@/components/ui/text-link";
import { EventList } from "@/features/events/event-list";
import {
  filterFromParams,
  MANAGE_PERMISSION,
  PAGE_SIZE,
  type EventFilter,
} from "@/features/events/model";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { hasPermission, loaded, serverApi } from "@/lib/api/server";
import { cn } from "@/lib/cn";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("events");
  return { title: t("title") };
}

const FILTERS: { value: EventFilter; href: string }[] = [
  { value: "upcoming", href: "/events" },
  { value: "past", href: "/events?period=past" },
  { value: "registered", href: "/events?registered=true" },
];

type EventsPageProps = {
  searchParams: Promise<{ period?: string; registered?: string; cursor?: string }>;
};

export default async function EventsPage({ searchParams }: EventsPageProps) {
  const t = await getTranslations("events");
  const params = await searchParams;
  const filter = filterFromParams(params);
  const api = await serverApi();
  const [page, canManage] = await Promise.all([
    api
      .GET("/api/v1/events", {
        params: {
          query: {
            period: filter === "past" ? "past" : "upcoming",
            registered: filter === "registered",
            cursor: params.cursor,
            limit: PAGE_SIZE,
          },
        },
      })
      .then(loaded),
    hasPermission(MANAGE_PERMISSION),
  ]);
  const current = FILTERS.find((item) => item.value === filter)!;
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        breadcrumb={[{ label: t("title") }]}
        actions={
          <>
            <Link href="/events/tickets" className={buttonVariants()}>
              <Icon icon={Ticket} />
              {t("tickets")}
            </Link>
            {canManage ? (
              <Link href="/events/new" className={buttonVariants({ variant: "primary" })}>
                <Icon icon={Plus} />
                {t("create")}
              </Link>
            ) : null}
          </>
        }
      />
      <nav aria-label={t("filters.label")} className="mb-4">
        <ul className="flex flex-wrap gap-2">
          {FILTERS.map((item) => (
            <li key={item.value}>
              <Link
                href={item.href}
                aria-current={item.value === filter ? "page" : undefined}
                className={cn(
                  buttonVariants({ size: "dense" }),
                  item.value === filter && "border-primary text-primary",
                )}
              >
                {t(`filters.${item.value}`)}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      {page.status !== "ok" ? (
        <ForbiddenState />
      ) : page.data.items.length === 0 ? (
        <Panel className="px-4">
          <EmptyState icon={CalendarDays} message={t(`empty.${filter}`)} />
        </Panel>
      ) : (
        <div className="flex flex-col gap-4">
          <Panel>
            <EventList items={page.data.items} />
          </Panel>
          {page.data.next_cursor ? (
            <TextLink
              href={`${current.href}${current.href.includes("?") ? "&" : "?"}cursor=${encodeURIComponent(page.data.next_cursor)}`}
            >
              {t("loadMore")}
            </TextLink>
          ) : null}
        </div>
      )}
    </>
  );
}
