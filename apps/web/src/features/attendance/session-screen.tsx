"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/overlay";
import { Panel, PanelBody } from "@/components/ui/panel";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tag } from "@/components/ui/tag";
import { offeringLabel, ScreenState } from "@/features/coursework/coursework";
import { TicketQr } from "@/features/events/ticket-qr";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";
import { formatTime } from "@/lib/format";

import { useNow } from "./attendance-shared";

type RosterEntry = components["schemas"]["AttendanceRosterEntryOut"];

const CODE_POLL_MS = 2000;
const ROSTER_POLL_MS = 5000;

/**
 * The teacher's screen for one meeting (§6.1): a QR code and six digits that change every 30 seconds, the live
 * count, and the roster with manual marks. The rotation is the server's: this screen only shows what it is told.
 */
export function SessionScreen({ sessionId }: { sessionId: string }) {
  const t = useTranslations("attendance.session");
  const api = useApi();
  const client = useQueryClient();

  const detail = useQuery({
    queryKey: ["attendance", "session", sessionId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/attendance/sessions/{session_id}", {
          params: { path: { session_id: sessionId } },
        }),
      ),
    refetchInterval: (query) => (query.state.data?.is_open === false ? false : ROSTER_POLL_MS),
  });
  const isOpen = detail.data?.is_open === true;
  const code = useQuery({
    queryKey: ["attendance", "code", sessionId],
    queryFn: async () => {
      const shown = unwrap(
        await api.GET("/api/v1/attendance/sessions/{session_id}/code", {
          params: { path: { session_id: sessionId } },
        }),
      );
      // The device clock may be off: the countdown is measured against the server's time.
      return { ...shown, clockOffset: Date.parse(shown.server_time) - Date.now() };
    },
    enabled: isOpen,
    refetchInterval: (query) => (query.state.data?.is_open === false ? false : CODE_POLL_MS),
  });
  const close = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/attendance/sessions/{session_id}/close", {
          params: { path: { session_id: sessionId } },
        }),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["attendance"] });
    },
  });

  if (!detail.data) {
    return (
      <ScreenState
        loading={detail.isLoading}
        error={detail.error}
        empty={false}
        emptyMessage=""
        errorMessage={t("error")}
        retryLabel={t("retry")}
        retry={() => void detail.refetch()}
      />
    );
  }
  const meeting = detail.data;
  return (
    <div className="flex flex-col gap-4">
      <Panel>
        <PanelBody>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-lg font-semibold break-words">
                {meeting.title || offeringLabel(meeting.offering)}
              </p>
              <p className="text-sm text-muted">{offeringLabel(meeting.offering)}</p>
              <p className="text-sm text-muted">
                {t("window", {
                  from: formatTime(meeting.opened_at),
                  to: formatTime(meeting.closed_at ?? meeting.expires_at),
                })}
              </p>
            </div>
            <Tag tone={meeting.is_open ? "success" : "neutral"}>
              {meeting.is_open ? t("statusOpen") : t("statusClosed")}
            </Tag>
          </div>
        </PanelBody>
      </Panel>
      {meeting.is_open ? (
        <Panel>
          <PanelBody>
            <div className="flex flex-col items-center gap-4 text-center sm:flex-row sm:items-start sm:text-left">
              <LiveCodeCard
                qr={code.data?.qr}
                digits={code.data?.digits}
                validUntil={code.data ? Date.parse(code.data.valid_until) : null}
                clockOffset={code.data?.clockOffset ?? 0}
                failed={code.isError}
              />
              <div className="flex min-w-0 flex-col gap-3">
                <p aria-live="polite" className="text-2xl font-semibold tabular">
                  {t("count", {
                    present: code.data?.present ?? meeting.present,
                    enrolled: code.data?.enrolled ?? meeting.enrolled,
                  })}
                </p>
                <p className="text-sm text-muted">{t("hint")}</p>
                {close.isError ? <Banner tone="danger" title={t("closeFailed")} /> : null}
                <div>
                  <Button
                    variant="secondary"
                    loading={close.isPending}
                    onClick={() => close.mutate()}
                  >
                    {t("close")}
                  </Button>
                </div>
              </div>
            </div>
          </PanelBody>
        </Panel>
      ) : (
        <Banner tone="info" title={t("closedNote")}>
          {t("count", { present: meeting.present, enrolled: meeting.enrolled })}
        </Banner>
      )}
      <Roster sessionId={sessionId} roster={meeting.roster} />
    </div>
  );
}

/** The code with its countdown, measured against the server's clock rather than the device's. */
function LiveCodeCard({
  qr,
  digits,
  validUntil,
  clockOffset,
  failed,
}: {
  qr: string | undefined;
  digits: string | undefined;
  validUntil: number | null;
  clockOffset: number;
  failed: boolean;
}) {
  const now = useNow();
  const secondsLeft =
    validUntil === null ? null : Math.max(0, Math.ceil((validUntil - (now + clockOffset)) / 1000));
  return <CodeCard qr={qr} digits={digits} secondsLeft={secondsLeft} failed={failed} />;
}

export function CodeCard({
  qr,
  digits,
  secondsLeft,
  failed,
}: {
  qr: string | undefined;
  digits: string | undefined;
  secondsLeft: number | null;
  failed: boolean;
}) {
  const t = useTranslations("attendance.session");
  if (failed) return <Banner tone="danger" title={t("codeFailed")} />;
  if (!qr || !digits || secondsLeft === null) {
    return (
      <div className="size-72 max-w-full animate-pulse border border-border" aria-busy="true" />
    );
  }
  return (
    <div className="flex flex-col items-center gap-2">
      <TicketQr code={qr} label={t("qrLabel")} className="size-72" />
      <p
        className="text-3xl font-mono font-semibold tracking-normal tabular"
        aria-label={t("digitsLabel")}
      >
        {digits.slice(0, 3)} {digits.slice(3)}
      </p>
      <p className="text-sm text-muted tabular">{t("rotatesIn", { seconds: secondsLeft })}</p>
    </div>
  );
}

export function Roster({ sessionId, roster }: { sessionId: string; roster: RosterEntry[] }) {
  const t = useTranslations("attendance.session");
  const [target, setTarget] = useState<RosterEntry | null>(null);
  return (
    <section aria-labelledby="attendance-roster" className="flex flex-col gap-2">
      <h2 id="attendance-roster" className="text-lg font-semibold">
        {t("roster")}
      </h2>
      {roster.length === 0 ? (
        <Panel>
          <PanelBody>
            <p className="text-muted">{t("rosterEmpty")}</p>
          </PanelBody>
        </Panel>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("columns.student")}</TableHead>
              <TableHead>{t("columns.group")}</TableHead>
              <TableHead>{t("columns.status")}</TableHead>
              <TableHead>{t("columns.method")}</TableHead>
              <TableHead>
                <span className="sr-only">{t("columns.actions")}</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {roster.map((entry) => (
              <TableRow key={entry.student_id}>
                <TableCell label={t("columns.student")}>{entry.display_name}</TableCell>
                <TableCell label={t("columns.group")}>{entry.group ?? "—"}</TableCell>
                <TableCell label={t("columns.status")}>
                  <Tag tone={entry.present ? "success" : "neutral"}>
                    {entry.present ? t("present") : t("absent")}
                  </Tag>
                </TableCell>
                <TableCell label={t("columns.method")}>
                  {entry.method ? t(`method.${entry.method}`) : "—"}
                </TableCell>
                <TableCell label={t("columns.actions")}>
                  <Button variant="tertiary" size="dense" onClick={() => setTarget(entry)}>
                    {entry.present ? t("unmark") : t("mark")}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      {target ? (
        <MarkDialog sessionId={sessionId} entry={target} onClose={() => setTarget(null)} />
      ) : null}
    </section>
  );
}

/** A manual change always carries a reason; the server audits it (§6.1). */
function MarkDialog({
  sessionId,
  entry,
  onClose,
}: {
  sessionId: string;
  entry: RosterEntry;
  onClose: () => void;
}) {
  const t = useTranslations("attendance.session");
  const api = useApi();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const [reason, setReason] = useState("");
  const [missing, setMissing] = useState(false);
  const wasPresent = entry.present;
  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.PUT("/api/v1/attendance/sessions/{session_id}/students/{student_id}", {
          params: { path: { session_id: sessionId, student_id: entry.student_id } },
          body: { present: !wasPresent, reason: reason.trim() },
        }),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["attendance", "session", sessionId] });
      onClose();
    },
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={wasPresent ? t("unmarkTitle") : t("markTitle")}
        description={entry.display_name}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="secondary">{t("cancel")}</Button>
            </DialogClose>
            <Button
              variant="primary"
              loading={save.isPending}
              onClick={() => {
                if (reason.trim().length < 3) return setMissing(true);
                save.mutate();
              }}
            >
              {wasPresent ? t("unmark") : t("mark")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {save.isError ? (
            <Banner tone="danger" title={t("markFailed")}>
              {errorMessage(save.error)}
            </Banner>
          ) : null}
          <Field
            label={t("reason")}
            helper={t("reasonHelp")}
            error={missing ? t("reasonRequired") : undefined}
            required
          >
            <Input
              value={reason}
              maxLength={300}
              onChange={(event) => {
                setReason(event.target.value);
                setMissing(false);
              }}
            />
          </Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}
