import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { ChatScreen } from "@/features/chat/chat-screen";
import { getCurrentUser } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("chat");
  return { title: t("title") };
}

export default async function ChatPage() {
  const result = await getCurrentUser();
  return <ChatScreen currentUserName={result.status === "ok" ? result.user.display_name : ""} />;
}
