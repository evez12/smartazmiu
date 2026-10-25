"use client";

import { useMutation } from "@tanstack/react-query";
import { RotateCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";
import { AudiencePicker, type AudienceChoice } from "@/features/audiences/audience-picker";
import { ApiRequestError, unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import { bakuInputToIso, isoToBakuInput } from "@/lib/format";

import { DESCRIPTION_MAX, TITLE_MAX, type EventItem } from "./model";

/** New event (with audience) or a change to an existing one; times are entered in Baku time. */
export function EventEditor({ event }: { event?: EventItem }) {
  const t = useTranslations("events.editor");
  const tAudience = useTranslations("audiences");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [title, setTitle] = useState(event?.title ?? "");
  const [description, setDescription] = useState(event?.description ?? "");
  const [startsAt, setStartsAt] = useState(event ? isoToBakuInput(event.starts_at) : "");
  const [endsAt, setEndsAt] = useState(event ? isoToBakuInput(event.ends_at) : "");
  const [roomCode, setRoomCode] = useState(event?.room?.code ?? "");
  const [location, setLocation] = useState(event?.location ?? "");
  const [capacity, setCapacity] = useState(event?.capacity ? String(event.capacity) : "");
  const [audience, setAudience] = useState<AudienceChoice>({ type: "university", target: null });
  const [submitted, setSubmitted] = useState(false);
  const [idempotencyKey] = useState(() => crypto.randomUUID());

  const capacityValue = capacity.trim() ? Number(capacity) : null;
  const errors = {
    title: !title.trim() ? t("titleRequired") : undefined,
    description: !description.trim() ? t("descriptionRequired") : undefined,
    times:
      !startsAt || !endsAt ? t("timesRequired") : endsAt <= startsAt ? t("timesOrder") : undefined,
    place: !roomCode.trim() && !location.trim() ? t("placeRequired") : undefined,
    capacity:
      capacityValue !== null && !(Number.isInteger(capacityValue) && capacityValue > 0)
        ? t("capacityInvalid")
        : undefined,
    audience:
      !event && audience.type !== "university" && !audience.target
        ? tAudience("required")
        : undefined,
  };
  const valid = Object.values(errors).every((error) => !error);

  const save = useMutation({
    mutationFn: async () => {
      const details = {
        title,
        description,
        starts_at: bakuInputToIso(startsAt),
        ends_at: bakuInputToIso(endsAt),
        room_code: roomCode.trim() || null,
        location,
        capacity: capacityValue,
      };
      if (event) {
        return unwrap(
          await api.PATCH("/api/v1/events/{event_id}", {
            params: { path: { event_id: event.id } },
            body: { ...details, version: event.version },
          }),
        );
      }
      return unwrap(
        await api.POST("/api/v1/events", {
          params: { header: { "Idempotency-Key": idempotencyKey } },
          body: {
            ...details,
            audience: { type: audience.type, target_id: audience.target?.id ?? null },
          },
        }),
      );
    },
    onSuccess: (saved) => {
      toast({ title: event ? t("saved") : t("published") });
      router.push(`/events/${saved.id}`);
      router.refresh();
    },
  });
  const conflict = save.error instanceof ApiRequestError && save.error.status === 409;

  const submit = (formEvent: FormEvent<HTMLFormElement>) => {
    formEvent.preventDefault();
    setSubmitted(true);
    if (valid) save.mutate();
  };
  const shown = (error: string | undefined) => (submitted ? error : undefined);

  return (
    <form onSubmit={submit} noValidate className="flex max-w-2xl flex-col gap-6">
      {save.isError ? (
        <Banner
          tone="danger"
          title={t("failed")}
          action={
            conflict ? (
              <Button size="dense" onClick={() => window.location.reload()}>
                <Icon icon={RotateCw} />
                {t("reload")}
              </Button>
            ) : undefined
          }
        >
          {errorMessage(save.error)}
        </Banner>
      ) : null}

      <Field label={t("titleLabel")} error={shown(errors.title)} required>
        <Input value={title} maxLength={TITLE_MAX} onChange={(e) => setTitle(e.target.value)} />
      </Field>
      <Field
        label={t("description")}
        helper={t("descriptionHelp")}
        error={shown(errors.description)}
        required
      >
        <Textarea
          rows={6}
          value={description}
          maxLength={DESCRIPTION_MAX}
          onChange={(e) => setDescription(e.target.value)}
        />
      </Field>

      <div className="flex flex-wrap gap-4">
        <Field label={t("startsAt")} helper={t("timesHelp")} error={shown(errors.times)} required>
          <Input
            type="datetime-local"
            className="w-60 tabular"
            value={startsAt}
            onChange={(e) => setStartsAt(e.target.value)}
          />
        </Field>
        <Field label={t("endsAt")} required>
          <Input
            type="datetime-local"
            className="w-60 tabular"
            value={endsAt}
            onChange={(e) => setEndsAt(e.target.value)}
          />
        </Field>
      </div>

      <div className="flex flex-wrap gap-4">
        <Field label={t("roomCode")} helper={t("roomCodeHelp")} error={shown(errors.place)}>
          <Input
            className="w-40"
            value={roomCode}
            maxLength={20}
            onChange={(e) => setRoomCode(e.target.value)}
          />
        </Field>
        <Field label={t("location")} helper={t("locationHelp")} className="min-w-0 flex-1">
          <Input value={location} maxLength={200} onChange={(e) => setLocation(e.target.value)} />
        </Field>
      </div>

      <Field label={t("capacity")} helper={t("capacityHelp")} error={shown(errors.capacity)}>
        <Input
          type="number"
          inputMode="numeric"
          min={1}
          className="w-32 tabular"
          value={capacity}
          onChange={(e) => setCapacity(e.target.value)}
        />
      </Field>

      {event ? null : (
        <AudiencePicker value={audience} onChange={setAudience} error={shown(errors.audience)} />
      )}

      <div>
        <Button type="submit" variant="primary" loading={save.isPending}>
          {event ? t("save") : t("publish")}
        </Button>
      </div>
    </form>
  );
}
