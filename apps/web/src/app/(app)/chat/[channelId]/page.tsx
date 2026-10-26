import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { ChatScreen } from "@/features/chat/chat-screen";
import { getCurrentUser } from "@/lib/api/server";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("chat");
  return { title: t("title") };
}

export default async function ChannelPage({ params }: { params: Promise<{ channelId: string }> }) {
  const { channelId } = await params;
  if (!UUID.test(channelId)) notFound();
  const result = await getCurrentUser();
  return (
    <ChatScreen
      channelId={channelId.toLowerCase()}
      currentUserName={result.status === "ok" ? result.user.display_name : ""}
    />
  );
}
