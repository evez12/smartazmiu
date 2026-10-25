import { Ticket } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody } from "@/components/ui/panel";
import { Tag } from "@/components/ui/tag";
import { TicketQr } from "@/features/events/ticket-qr";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { loaded, serverApi } from "@/lib/api/server";
import { formatDateTimeRange } from "@/lib/format";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("events");
  return { title: t("tickets") };
}

export default async function TicketsPage() {
  const t = await getTranslations("events");
  const api = await serverApi();
  const result = await api.GET("/api/v1/me/tickets").then(loaded);
  const header = (
    <PageHeader
      title={t("tickets")}
      description={t("ticket.ticketsDescription")}
      breadcrumb={[{ label: t("title"), href: "/events" }, { label: t("tickets") }]}
    />
  );
  if (result.status !== "ok") {
    return (
      <>
        {header}
        <ForbiddenState />
      </>
    );
  }
  return (
    <>
      {header}
      {result.data.items.length === 0 ? (
        <Panel className="px-4">
          <EmptyState icon={Ticket} message={t("ticket.ticketsEmpty")} />
        </Panel>
      ) : (
        <ul className="grid gap-4 md:grid-cols-2">
          {result.data.items.map((event) => {
            const code = event.my_registration?.ticket_code;
            return (
              <li key={event.id}>
                <Panel>
                  <PanelBody className="flex flex-col gap-3">
                    <h2 className="font-medium break-words">
                      <Link href={`/events/${event.id}`} className="text-primary hover:underline">
                        {event.title}
                      </Link>
                    </h2>
                    <p className="text-sm text-muted tabular">
                      {formatDateTimeRange(event.starts_at, event.ends_at)} ({t("bakuTime")})
                    </p>
                    {code ? (
                      <>
                        <TicketQr code={code} label={t("ticket.qrLabel", { title: event.title })} />
                        <p className="font-mono text-xs break-all text-muted">{code}</p>
                      </>
                    ) : (
                      <Tag tone="danger">{t("ticket.cancelledEvent")}</Tag>
                    )}
                  </PanelBody>
                </Panel>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
