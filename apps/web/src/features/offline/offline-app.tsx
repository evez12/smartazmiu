"use client";

import { CloudOff } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { Wordmark } from "@/components/brand/wordmark";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { SkeletonText } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MessageMarkdown } from "@/features/chat/markdown";
import { bakuToday, type Schedule } from "@/features/schedule/model";
import { WeekView } from "@/features/schedule/schedule-views";
import { cn } from "@/lib/cn";
import { getSnapshot, listSnapshots, readDevice, type Snapshot } from "@/lib/offline/store";
import { leaveDevice } from "@/lib/offline/sign-out";
import { wipeOfflineData } from "@/lib/offline/wipe";
import { useFormatters } from "@/lib/use-format";

import { splitWeeks, type ChannelHistory, type ChannelList, type OfflineMessage } from "./model";
import { OfflineBanner } from "./notices";
import { useOnline } from "./use-online";

export type Loaded = {
  schedule: Snapshot<Schedule> | null;
  channels: Snapshot<ChannelList> | null;
  histories: Snapshot<ChannelHistory>[];
};

type View =
  | { status: "loading" }
  | { status: "none" | "disabled" | "expired" | "unavailable" | "signedOut" }
  | ({ status: "ready" } & Loaded);

async function load(): Promise<View> {
  const device = await readDevice();
  if (!device) return { status: "none" };
  // The session ended at an absolute time (D-040): the data goes with it, even though no server can be asked.
  if (device.sessionEndsAt * 1000 <= Date.now()) {
    await wipeOfflineData();
    return { status: "expired" };
  }
  if (!device.enabled) return { status: "disabled" };
  const [schedule, channels, histories] = await Promise.all([
    getSnapshot<Schedule>(device.userId, "schedule"),
    getSnapshot<ChannelList>(device.userId, "channels"),
    listSnapshots<ChannelHistory>(device.userId, "channel"),
  ]);
  return { status: "ready", schedule, channels, histories };
}

/**
 * The page the service worker shows when a navigation fails (D-117). It reads what the signed-in user stored on this
 * device, read-only, and is the same document for everyone: it holds no data of its own.
 */
export function OfflineApp() {
  const t = useTranslations("offline.page");
  const online = useOnline();
  const router = useRouter();
  const [view, setView] = useState<View>({ status: "loading" });

  useEffect(() => {
    let mounted = true;
    load().then(
      (loaded) => mounted && setView(loaded),
      () => mounted && setView({ status: "unavailable" }),
    );
    return () => {
      mounted = false;
    };
  }, []);

  const signOut = async () => {
    // The server session ends when the app next loads with a connection (D-117), so the pending flag is set here too.
    await leaveDevice(false);
    if (navigator.onLine) router.push("/");
    else setView({ status: "signedOut" });
  };
  const lastUpdated = view.status === "ready" ? (view.schedule?.savedAt ?? null) : null;

  return (
    <div className="flex min-h-dvh flex-col bg-bg-subtle">
      <header className="sticky top-0 z-40 flex h-[calc(56px+env(safe-area-inset-top))] shrink-0 items-center gap-2 border-b border-border bg-surface px-4 pt-[env(safe-area-inset-top)]">
        <Wordmark />
        <div className="flex-1" />
        {view.status === "ready" || view.status === "disabled" ? (
          <Button variant="tertiary" size="dense" onClick={() => void signOut()}>
            {t("signOut")}
          </Button>
        ) : null}
      </header>
      <main id="main" className="mx-auto w-full max-w-[1200px] flex-1 px-4 py-6 md:px-6 lg:py-8">
        <PageHeader title={t("title")} description={t("description")} />
        <div className="flex flex-col gap-4">
          {online ? (
            <Banner
              tone="success"
              title={t("onlineTitle")}
              action={
                <Button asChild variant="primary" size="dense">
                  <Link href="/">{t("goToApp")}</Link>
                </Button>
              }
            >
              {t("onlineBody")}
            </Banner>
          ) : (
            <OfflineBanner variant="cached" lastUpdated={lastUpdated} />
          )}
          <Content view={view} />
        </div>
      </main>
    </div>
  );
}

function Content({ view }: { view: View }) {
  const t = useTranslations("offline.page");
  if (view.status === "loading") return <SkeletonText lines={6} />;
  if (view.status === "ready") return <StoredContent data={view} />;
  return (
    <Panel className="p-4">
      <EmptyState icon={CloudOff} message={t(`empty.${view.status}`)} />
    </Panel>
  );
}

/** The stored schedule and channels as tabs; `today` is fixed only where a stable picture is needed (specimens). */
export function StoredContent({ data, today = bakuToday() }: { data: Loaded; today?: string }) {
  const t = useTranslations("offline.page");
  return (
    <Tabs defaultValue="schedule">
      <TabsList aria-label={t("sections")}>
        <TabsTrigger value="schedule">{t("scheduleTab")}</TabsTrigger>
        <TabsTrigger value="channels">{t("channelsTab")}</TabsTrigger>
      </TabsList>
      <TabsContent value="schedule">
        <StoredSchedule snapshot={data.schedule} today={today} />
      </TabsContent>
      <TabsContent value="channels">
        <StoredChannels channels={data.channels} histories={data.histories} />
      </TabsContent>
    </Tabs>
  );
}

function StoredSchedule({
  snapshot,
  today,
}: {
  snapshot: Snapshot<Schedule> | null;
  today: string;
}) {
  const t = useTranslations("offline.page");
  const weeks = useMemo(
    () => (snapshot ? splitWeeks(snapshot.data).map((week) => ({ ...week, today })) : []),
    [snapshot, today],
  );
  const [chosen, setChosen] = useState<number | null>(null);
  if (weeks.length === 0) {
    return <EmptyState icon={CloudOff} message={t("empty.noSchedule")} />;
  }
  // The week that contains today when it is stored, otherwise the first stored week.
  const containing = weeks.findIndex((week) => week.start <= today && today <= week.end);
  const index = chosen ?? Math.max(containing, 0);
  return (
    <div className="flex flex-col gap-4">
      <div role="group" aria-label={t("weeks")} className="flex gap-2">
        {weeks.map((week, position) => (
          <Button
            key={week.start}
            variant="secondary"
            size="dense"
            aria-pressed={position === index}
            className={cn(position === index && "border-primary bg-bg-subtle")}
            onClick={() => setChosen(position)}
          >
            {position === 0 ? t("thisWeek") : t("nextWeek")}
          </Button>
        ))}
      </div>
      <WeekView schedule={weeks[index]!} links={false} />
    </div>
  );
}

function StoredChannels({
  channels,
  histories,
}: {
  channels: Snapshot<ChannelList> | null;
  histories: Snapshot<ChannelHistory>[];
}) {
  const t = useTranslations("offline.page");
  const [openId, setOpenId] = useState<string | null>(null);
  const list = channels?.data.channels ?? [];
  const open = histories.find((entry) => entry.data.channel.id === openId);
  if (list.length === 0) return <EmptyState icon={CloudOff} message={t("empty.noChannels")} />;
  if (open) {
    return (
      <div className="flex flex-col gap-4">
        <div>
          <Button variant="secondary" size="dense" onClick={() => setOpenId(null)}>
            {t("backToChannels")}
          </Button>
        </div>
        <Panel aria-label={open.data.channel.name} className="px-4">
          <h2 className="border-b border-border py-3 text-md font-semibold">
            {open.data.channel.name}
          </h2>
          {open.data.messages.length === 0 ? (
            <EmptyState message={t("empty.noMessages")} />
          ) : (
            <ul>
              {open.data.messages.map((message) => (
                <StoredMessage key={message.id} message={message} />
              ))}
            </ul>
          )}
        </Panel>
      </div>
    );
  }
  return (
    <Panel>
      <ul aria-label={t("channelList")}>
        {list.map((channel) => (
          <li key={channel.id} className="border-b border-border last:border-b-0">
            <button
              type="button"
              onClick={() => setOpenId(channel.id)}
              className="flex min-h-11 w-full flex-col items-start justify-center px-4 py-2 text-left hover:bg-bg-subtle"
            >
              <span className="font-medium break-words">{channel.name}</span>
              {channel.context ? (
                <span className="text-sm break-words text-muted">{channel.context}</span>
              ) : null}
            </button>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function StoredMessage({ message }: { message: OfflineMessage }) {
  const t = useTranslations("offline.page");
  const tChat = useTranslations("chat");
  const { formatDateTime } = useFormatters();
  const author = message.anonymous
    ? tChat("anonymous")
    : (message.authorName ?? tChat("deletedUser"));
  return (
    <li className="flex flex-col gap-1 border-b border-border py-3 last:border-b-0">
      <p className="flex flex-wrap items-baseline gap-x-2 text-sm text-muted">
        <span className="font-medium break-words text-text">{author}</span>
        <time dateTime={message.createdAt} className="tabular">
          {formatDateTime(message.createdAt)}
        </time>
        {message.edited ? <span>{t("edited")}</span> : null}
      </p>
      {message.state === "visible" ? (
        <MessageMarkdown body={message.body} mentions={message.mentions} currentUserId="" />
      ) : (
        <p className="text-muted">{t(`state.${message.state}`)}</p>
      )}
      {message.attachmentNames.length ? (
        <p className="text-sm break-words text-muted">
          {t("attachments", { names: message.attachmentNames.join(", ") })}
        </p>
      ) : null}
    </li>
  );
}
