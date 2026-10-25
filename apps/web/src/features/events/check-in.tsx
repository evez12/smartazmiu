"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, CameraOff, CheckCircle2, CircleAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { SkeletonTable } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tag } from "@/components/ui/tag";
import { ApiRequestError, unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import { formatTime } from "@/lib/format";

type Outcome = { tone: "success" | "danger"; title: string; body?: string };

/** Chromium's barcode detector; absent elsewhere, where the code is scanned by a device or typed. */
type Detector = { detect(source: HTMLVideoElement): Promise<{ rawValue: string }[]> };
type DetectorConstructor = new (options: { formats: string[] }) => Detector;

function detectorClass(): DetectorConstructor | null {
  const candidate = (globalThis as { BarcodeDetector?: DetectorConstructor }).BarcodeDetector;
  return candidate ?? null;
}

const SCAN_INTERVAL_MS = 400;
// The same code stays in front of the camera for a moment; it is submitted once.
const SAME_CODE_PAUSE_MS = 3000;

export function CheckInDesk({ eventId }: { eventId: string }) {
  const t = useTranslations("events.checkIn");
  const api = useApi();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const [code, setCode] = useState("");
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const attendeesKey = ["events", eventId, "attendees"];

  const attendees = useQuery({
    queryKey: attendeesKey,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/events/{event_id}/attendees", {
          params: { path: { event_id: eventId } },
        }),
      ),
  });
  const admit = useMutation({
    mutationFn: async (body: { code: string } | { registration_id: string }) =>
      unwrap(
        await api.POST("/api/v1/events/{event_id}/check-ins", {
          params: { path: { event_id: eventId } },
          body,
        }),
      ),
    onSuccess: (person) => {
      setOutcome({
        tone: "success",
        title: person.group
          ? t("admittedGroup", { name: person.name, group: person.group })
          : t("admitted", { name: person.name }),
      });
    },
    onError: (error) => {
      const details = error instanceof ApiRequestError ? error.details : {};
      const already =
        error instanceof ApiRequestError && error.code === "events.already_checked_in";
      setOutcome({
        tone: "danger",
        title: t("refused"),
        body: already
          ? t("already", {
              name: String(details.name ?? ""),
              time: formatTime(String(details.checked_in_at ?? "")),
            })
          : errorMessage(error),
      });
    },
    onSettled: () => {
      setCode("");
      input.current?.focus();
      queryClient.invalidateQueries({ queryKey: attendeesKey });
    },
  });

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (code.trim()) admit.mutate({ code: code.trim() });
  };

  return (
    <div className="flex flex-col gap-6">
      <Panel>
        <PanelBody className="flex flex-col gap-4">
          <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
            <Field label={t("code")} helper={t("codeHelp")} className="min-w-0 flex-1">
              <Input
                ref={input}
                value={code}
                autoFocus
                autoComplete="off"
                spellCheck={false}
                className="font-mono"
                onChange={(event) => setCode(event.target.value)}
              />
            </Field>
            <Button type="submit" variant="primary" loading={admit.isPending}>
              {t("submit")}
            </Button>
          </form>
          <CameraScanner onCode={(scanned) => admit.mutate({ code: scanned })} />
          <div aria-live="assertive">
            {outcome ? (
              <Banner tone={outcome.tone} title={outcome.title}>
                {outcome.body}
              </Banner>
            ) : null}
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader
          title={t("attendees")}
          description={
            attendees.data
              ? t("summary", {
                  checkedIn: attendees.data.checked_in,
                  going: attendees.data.going,
                })
              : undefined
          }
        />
        {attendees.isPending ? (
          <SkeletonTable rows={4} className="p-4" />
        ) : attendees.isError ? (
          <PanelBody>
            <Banner tone="danger" title={t("refused")}>
              {errorMessage(attendees.error)}
            </Banner>
          </PanelBody>
        ) : attendees.data.items.length === 0 ? (
          <PanelBody>
            <p className="text-muted">{t("attendeesEmpty")}</p>
          </PanelBody>
        ) : (
          <Table>
            <TableCaption>{t("attendees")}</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>{t("columns.name")}</TableHead>
                <TableHead>{t("columns.group")}</TableHead>
                <TableHead>{t("columns.state")}</TableHead>
                <TableHead>{t("columns.action")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {attendees.data.items.map((person) => (
                <TableRow key={person.registration_id}>
                  <TableCell label={t("columns.name")}>{person.name}</TableCell>
                  <TableCell label={t("columns.group")}>{person.group ?? t("noGroup")}</TableCell>
                  <TableCell label={t("columns.state")}>
                    {person.checked_in_at ? (
                      <Tag tone="success" icon={CheckCircle2}>
                        {person.check_in_method === "manual"
                          ? `${formatTime(person.checked_in_at)} · ${t("byHand")}`
                          : formatTime(person.checked_in_at)}
                      </Tag>
                    ) : (
                      <Tag>{t("notYet")}</Tag>
                    )}
                  </TableCell>
                  <TableCell label={t("columns.action")}>
                    {person.checked_in_at ? null : (
                      <Button
                        size="dense"
                        onClick={() => admit.mutate({ registration_id: person.registration_id })}
                      >
                        {t("manual")}
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Panel>
    </div>
  );
}

/** Camera preview that reads QR codes where the browser can; hidden where it cannot. */
function CameraScanner({ onCode }: { onCode: (code: string) => void }) {
  const t = useTranslations("events.checkIn");
  const video = useRef<HTMLVideoElement>(null);
  const [supported, setSupported] = useState(false);
  const [active, setActive] = useState(false);
  const [failed, setFailed] = useState(false);
  const callback = useRef(onCode);

  useEffect(() => {
    callback.current = onCode;
  }, [onCode]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      setSupported(detectorClass() !== null && Boolean(navigator.mediaDevices?.getUserMedia));
    });
    return () => window.clearTimeout(id);
  }, []);

  useEffect(() => {
    const Detector = detectorClass();
    if (!active || !Detector) return;
    let stream: MediaStream | null = null;
    let timer = 0;
    let last = { code: "", at: 0 };
    let stopped = false;
    const detector = new Detector({ formats: ["qr_code"] });
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "environment" } })
      .then(async (media) => {
        if (stopped) return media.getTracks().forEach((track) => track.stop());
        stream = media;
        if (!video.current) return;
        video.current.srcObject = media;
        await video.current.play();
        timer = window.setInterval(async () => {
          if (!video.current) return;
          const [found] = await detector.detect(video.current).catch(() => []);
          const now = Date.now();
          if (found && (found.rawValue !== last.code || now - last.at > SAME_CODE_PAUSE_MS)) {
            last = { code: found.rawValue, at: now };
            callback.current(found.rawValue);
          }
        }, SCAN_INTERVAL_MS);
      })
      .catch(() => {
        setFailed(true);
        setActive(false);
      });
    return () => {
      stopped = true;
      window.clearInterval(timer);
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, [active]);

  if (!supported) return null;
  return (
    <div className="flex flex-col items-start gap-3">
      <Button
        onClick={() => {
          setFailed(false);
          setActive((value) => !value);
        }}
      >
        <Icon icon={active ? CameraOff : Camera} />
        {active ? t("stopScan") : t("scan")}
      </Button>
      {active ? (
        <video
          ref={video}
          aria-label={t("cameraLabel")}
          muted
          playsInline
          className="aspect-square w-full max-w-xs rounded-panel border border-border bg-bg-subtle object-cover"
        />
      ) : null}
      {failed ? (
        <p className="flex items-center gap-2 text-sm text-danger">
          <Icon icon={CircleAlert} />
          {t("cameraFailed")}
        </p>
      ) : null}
    </div>
  );
}
