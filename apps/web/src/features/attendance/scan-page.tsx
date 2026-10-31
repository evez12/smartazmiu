"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Camera, CircleCheck } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Panel, PanelBody } from "@/components/ui/panel";
import { offeringLabel } from "@/features/coursework/coursework";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import { formatTime } from "@/lib/format";

import { startScanning } from "./scan-loop";

type Phase = "idle" | "starting" | "scanning" | "unavailable";
type Code = { qr: string } | { digits: string };

/** Only codes of this app are sent to the server; any other QR the camera happens to see is ignored. */
const CODE_PREFIX = "SAT1.";

/**
 * The student's check-in: scan the teacher's QR code with the camera, or type the six digits shown under it.
 * Typing is always available, so a missing camera, a refused permission or a dark room never blocks a student.
 */
export function ScanPage() {
  const t = useTranslations("attendance.scan");
  const api = useApi();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const videoRef = useRef<HTMLVideoElement>(null);
  const stopRef = useRef<(() => void) | null>(null);
  const sentRef = useRef(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [digits, setDigits] = useState("");
  const [digitsError, setDigitsError] = useState(false);

  const stopCamera = () => {
    stopRef.current?.();
    stopRef.current = null;
    // srcObject is a MediaStream here; it is not tested with instanceof because some in-app browsers lack the class.
    const stream = videoRef.current?.srcObject as MediaStream | null | undefined;
    stream?.getTracks?.().forEach((track) => track.stop());
    if (videoRef.current) videoRef.current.srcObject = null;
  };
  useEffect(() => stopCamera, []);

  const checkIn = useMutation({
    mutationFn: async (code: Code) =>
      unwrap(await api.POST("/api/v1/attendance/check-in", { body: code })),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["attendance", "my"] }),
    onSettled: () => {
      // One answer per scan: the camera stops, so a wrong code is not sent again 4 times a second.
      stopCamera();
      setPhase("idle");
      sentRef.current = false;
    },
  });

  const startCamera = async () => {
    checkIn.reset();
    setPhase("starting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });
      const video = videoRef.current;
      if (!video) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      video.srcObject = stream;
      await video.play();
      stopRef.current = startScanning(video, (text) => {
        if (!text.startsWith(CODE_PREFIX) || sentRef.current) return;
        sentRef.current = true;
        checkIn.mutate({ qr: text });
      });
      setPhase("scanning");
    } catch {
      stopCamera();
      setPhase("unavailable");
    }
  };

  const submitDigits = (event: FormEvent) => {
    event.preventDefault();
    const typed = digits.replace(/\s/g, "");
    if (!/^\d{6}$/.test(typed)) return setDigitsError(true);
    setDigitsError(false);
    checkIn.mutate({ digits: typed });
  };

  const done = checkIn.data;
  return (
    <div className="flex max-w-2xl flex-col gap-4">
      {done ? (
        <Banner tone="success" title={done.already_present ? t("alreadyDone") : t("done")}>
          <span className="flex items-center gap-2">
            <CircleCheck aria-hidden className="size-4 shrink-0" />
            {t("doneDetail", {
              course: offeringLabel(done.offering),
              time: formatTime(done.checked_in_at),
            })}
          </span>
        </Banner>
      ) : null}
      {checkIn.isError ? (
        <Banner tone="danger" title={t("failed")}>
          {errorMessage(checkIn.error)}
        </Banner>
      ) : null}
      {phase === "unavailable" ? <Banner tone="warning" title={t("noCamera")} /> : null}
      <Panel>
        <PanelBody>
          <div className="flex flex-col gap-4">
            <div
              className={phase === "scanning" ? "block" : "hidden"}
              aria-hidden={phase !== "scanning"}
            >
              <video
                ref={videoRef}
                muted
                playsInline
                aria-label={t("cameraLabel")}
                className="aspect-square w-full max-w-sm border border-border bg-surface object-cover"
              />
              <p className="mt-2 text-sm text-muted">{t("aim")}</p>
            </div>
            <div className="flex flex-wrap gap-3">
              {phase === "scanning" ? (
                <Button
                  variant="secondary"
                  onClick={() => {
                    stopCamera();
                    setPhase("idle");
                  }}
                >
                  {t("stop")}
                </Button>
              ) : (
                <Button
                  variant="primary"
                  loading={phase === "starting"}
                  onClick={() => void startCamera()}
                >
                  <Camera aria-hidden className="size-4" />
                  {done || checkIn.isError ? t("scanAgain") : t("start")}
                </Button>
              )}
              <Button asChild variant="tertiary">
                <Link href="/attendance">{t("back")}</Link>
              </Button>
            </div>
          </div>
        </PanelBody>
      </Panel>
      <Panel>
        <PanelBody>
          <form noValidate onSubmit={submitDigits} className="flex flex-col gap-4">
            <Field
              label={t("digitsLabel")}
              helper={t("digitsHelp")}
              error={digitsError ? t("digitsInvalid") : undefined}
            >
              <Input
                value={digits}
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={7}
                className="font-mono tabular"
                onChange={(event) => {
                  setDigits(event.target.value.replace(/[^\d\s]/g, ""));
                  setDigitsError(false);
                }}
              />
            </Field>
            <div>
              <Button type="submit" variant="secondary" loading={checkIn.isPending}>
                {t("submitDigits")}
              </Button>
            </div>
          </form>
        </PanelBody>
      </Panel>
    </div>
  );
}
