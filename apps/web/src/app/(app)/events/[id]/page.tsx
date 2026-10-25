import { Pencil, ScanLine } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Banner } from "@/components/ui/banner";
import { buttonVariants } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { CancelEventButton } from "@/features/events/cancel-event-button";
import { EventFacts, EventTags } from "@/features/events/event-facts";
import { CHECK_IN_PERMISSION, hasEnded, MANAGE_PERMISSION } from "@/features/events/model";
import { Rsvp } from "@/features/events/rsvp";
import { TicketQr } from "@/features/events/ticket-qr";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { hasPermission, loaded, serverApi } from "@/lib/api/server";

type EventPageProps = { params: Promise<{ id: string }> };

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("events");
  return { title: t("title") };
}

export default async function EventPage({ params }: EventPageProps) {
  const t = await getTranslations("events");
  const { id } = await params;
  const api = await serverApi();
  const [result, canManage, canCheckIn] = await Promise.all([
    api.GET("/api/v1/events/{event_id}", { params: { path: { event_id: id } } }).then(loaded),
    hasPermission(MANAGE_PERMISSION),
    hasPermission(CHECK_IN_PERMISSION),
  ]);
  if (result.status !== "ok") return <ForbiddenState />;
  const event = result.data;
  const open = event.status === "published" && !hasEnded(event);
  const ticket = event.my_registration?.ticket_code;
  return (
    <>
      <PageHeader
        title={event.title}
        breadcrumb={[{ label: t("title"), href: "/events" }, { label: event.title }]}
        actions={
          open && (canManage || canCheckIn) ? (
            <>
              {canCheckIn ? (
                <Link href={`/events/${event.id}/check-in`} className={buttonVariants()}>
                  <Icon icon={ScanLine} />
                  {t("staff.checkIn")}
                </Link>
              ) : null}
              {canManage ? (
                <>
                  <Link href={`/events/${event.id}/edit`} className={buttonVariants()}>
                    <Icon icon={Pencil} />
                    {t("staff.edit")}
                  </Link>
                  <CancelEventButton eventId={event.id} />
                </>
              ) : null}
            </>
          ) : undefined
        }
      />
      <div className="flex flex-col gap-6">
        <Panel>
          <PanelBody className="flex flex-col gap-6">
            <EventTags event={event} />
            <EventFacts event={event} />
            <p className="max-w-[75ch] break-words whitespace-pre-line text-text">
              {event.description}
            </p>
            {open ? <Rsvp event={event} /> : null}
          </PanelBody>
        </Panel>

        {event.my_registration?.status === "going" ? (
          <Panel>
            <PanelHeader
              title={t("ticket.title")}
              description={ticket ? t("ticket.hint") : undefined}
            />
            <PanelBody>
              {ticket ? (
                <div className="flex flex-col items-start gap-3">
                  <TicketQr code={ticket} label={t("ticket.qrLabel", { title: event.title })} />
                  <p className="text-sm text-muted">{t("ticket.code")}</p>
                  <p className="font-mono text-sm break-all">{ticket}</p>
                </div>
              ) : (
                <Banner tone="warning" title={t("status.cancelled")}>
                  {t("ticket.cancelledEvent")}
                </Banner>
              )}
            </PanelBody>
          </Panel>
        ) : null}
      </div>
    </>
  );
}
