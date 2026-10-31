import { redirect } from "next/navigation";

/** Tag pages are the forum list filtered by one tag (§8 Sprint 12); one implementation serves both addresses. */
export default async function TagRoute({ params }: { params: Promise<{ tag: string }> }) {
  const { tag } = await params;
  redirect(`/forum?tag=${encodeURIComponent(tag)}`);
}
