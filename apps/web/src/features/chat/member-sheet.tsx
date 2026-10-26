"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Flag, MessageSquare, UserX } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Dialog, DialogContent, Sheet } from "@/components/ui/overlay";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { ReportDialog } from "@/features/reports/report-dialog";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";

import { AuthorBadge, useBadgeLabel } from "./author-badge";
import { chatKeys, type Author } from "./model";
import { PresenceDot } from "./presence-dot";
import { useChannels, useChatRuntime, useMembers } from "./runtime";

/** The channel's members (§5.8 addition, D-063); a member opens a card to start a DM or block (§5.4). */
export function MemberSheet({
  channelId,
  open,
  onOpenChange,
}: {
  channelId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations("chat");
  const runtime = useChatRuntime();
  const [selected, setSelected] = useState<Author | null>(null);
  const members = useMembers(channelId);

  const shown = members.data;
  useEffect(() => {
    if (open && shown) runtime.watchPresence(shown.map((member) => member.id));
  }, [open, runtime, shown]);

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange} title={t("membersTitle")} side="right">
        {members.isPending ? (
          <div aria-busy="true" className="flex flex-col gap-3 p-4">
            {Array.from({ length: 6 }, (_, index) => (
              <Skeleton key={index} className="h-8 w-full" />
            ))}
          </div>
        ) : members.isError ? (
          <div className="flex flex-col items-start gap-2 p-4">
            <p className="text-sm text-muted">{t("membersFailed")}</p>
            <Button size="dense" onClick={() => members.refetch()}>
              {t("retry")}
            </Button>
          </div>
        ) : (
          <ul className="flex flex-col p-2">
            {members.data.map((member) => (
              <li key={member.id}>
                <button
                  type="button"
                  onClick={() => setSelected(member)}
                  className="flex min-h-11 w-full items-center gap-3 rounded-control px-2 py-1 text-left hover:bg-bg-subtle"
                >
                  <span className="relative shrink-0">
                    <Avatar
                      name={member.display_name}
                      src={member.photo_url ?? undefined}
                      size={32}
                      decorative
                    />
                    <PresenceDot userId={member.id} className="absolute -right-0.5 -bottom-0.5" />
                  </span>
                  <span className="min-w-0 flex-1 truncate">
                    {member.display_name}
                    {member.id === runtime.currentUserId ? ` (${t("you")})` : ""}
                  </span>
                  <AuthorBadge author={member} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
      {selected ? (
        <UserCard
          person={selected}
          onClose={() => setSelected(null)}
          onOpened={() => {
            setSelected(null);
            onOpenChange(false);
          }}
        />
      ) : null}
    </>
  );
}

function UserCard({
  person,
  onClose,
  onOpened,
}: {
  person: Author;
  onClose: () => void;
  onOpened: () => void;
}) {
  const t = useTranslations("chat");
  const badgeLabel = useBadgeLabel();
  const tReports = useTranslations("reports");
  const api = useApi();
  const router = useRouter();
  const queryClient = useQueryClient();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const runtime = useChatRuntime();
  const channels = useChannels();
  const blocked = channels.data?.blocked_user_ids.includes(person.id) ?? false;
  const isMe = person.id === runtime.currentUserId;
  const [reporting, setReporting] = useState(false);

  const openDm = useMutation({
    mutationFn: async () =>
      unwrap(await api.POST("/api/v1/chat/dm", { body: { user_id: person.id } })),
    onSuccess: async (channel) => {
      await queryClient.invalidateQueries({ queryKey: chatKeys.channels });
      onOpened();
      router.push(`/chat/${channel.id}`);
    },
  });
  const toggleBlock = useMutation({
    mutationFn: async () => {
      const path = { params: { path: { user_id: person.id } } };
      unwrap(
        blocked
          ? await api.DELETE("/api/v1/users/{user_id}/block", path)
          : await api.POST("/api/v1/users/{user_id}/block", path),
      );
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: chatKeys.channels });
      toast({ tone: "success", title: blocked ? t("user.unblocked") : t("user.blocked") });
    },
  });
  const failure = openDm.error ?? toggleBlock.error;

  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent
        title={person.display_name}
        description={badgeLabel(person)}
        footer={
          isMe ? undefined : (
            <>
              <Button variant="tertiary" onClick={() => setReporting(true)}>
                <Icon icon={Flag} />
                {tReports("action")}
              </Button>
              <Button loading={toggleBlock.isPending} onClick={() => toggleBlock.mutate()}>
                <Icon icon={UserX} />
                {blocked ? t("user.unblock") : t("user.block")}
              </Button>
              <Button variant="primary" loading={openDm.isPending} onClick={() => openDm.mutate()}>
                <Icon icon={MessageSquare} />
                {t("user.message")}
              </Button>
            </>
          )
        }
      >
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Avatar
              name={person.display_name}
              src={person.photo_url ?? undefined}
              size={64}
              decorative
            />
            <PresenceDot userId={person.id} />
          </div>
          {blocked ? <p className="text-sm text-muted">{t("user.blockedNote")}</p> : null}
          {failure ? (
            <p role="alert" className="text-sm text-danger">
              {errorMessage(failure)}
            </p>
          ) : null}
        </div>
      </DialogContent>
      {reporting ? (
        <ReportDialog
          open={reporting}
          onOpenChange={setReporting}
          targetType="user"
          targetId={person.id}
        />
      ) : null}
    </Dialog>
  );
}
