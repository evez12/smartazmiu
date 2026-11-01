"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

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
import { useToast } from "@/components/ui/toast";
import { OfferingField, offeringLabel, ScreenState } from "@/features/coursework/coursework";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import { bakuInputToIso, formatDateTimeRange, isoToBakuInput } from "@/lib/format";

import type { ExamOverlap, ExamSlot } from "./model";

type Errors = Partial<Record<"offering" | "starts" | "ends", string>>;

/** The dean's office: add, move and remove exams, and see which ones collide (§13.4, D-097). */
export function SlotsAdmin() {
  const t = useTranslations("exams.admin");
  const api = useApi();
  const client = useQueryClient();
  const [past, setPast] = useState(false);
  const query = useQuery({
    queryKey: ["exams", "slots", past],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/exams/slots", { params: { query: { include_past: past } } }))
        .items,
  });
  const items = query.data ?? [];
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-3">
        <Button asChild variant="secondary">
          <Link href="/admin/imports">{t("importLink")}</Link>
        </Button>
        <Button variant="tertiary" onClick={() => setPast((value) => !value)}>
          {past ? t("hidePast") : t("showPast")}
        </Button>
      </div>
      <CreateForm onSaved={() => void client.invalidateQueries({ queryKey: ["exams", "slots"] })} />
      <ScreenState
        loading={query.isLoading}
        error={query.error}
        empty={!query.isLoading && !query.isError && items.length === 0}
        emptyMessage={t("empty")}
        errorMessage={t("error")}
        retryLabel={t("retry")}
        retry={() => void query.refetch()}
      />
      {items.length > 0 ? <SlotTable items={items} /> : null}
    </div>
  );
}

export function Overlaps({ overlaps }: { overlaps: ExamOverlap[] }) {
  const t = useTranslations("exams.admin");
  if (overlaps.length === 0) return null;
  return (
    <Banner tone="warning" title={t("overlapTitle")}>
      <ul className="list-disc pl-4">
        {overlaps.map((overlap) => (
          <li key={overlap.slot_id}>
            {t(`overlap.${overlap.kind}`, {
              course: overlap.offering.subject_name,
              when: formatDateTimeRange(overlap.starts_at, overlap.ends_at),
            })}
          </li>
        ))}
      </ul>
    </Banner>
  );
}

function CreateForm({ onSaved }: { onSaved: () => void }) {
  const t = useTranslations("exams.admin");
  const api = useApi();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [offering, setOffering] = useState("");
  const [starts, setStarts] = useState("");
  const [ends, setEnds] = useState("");
  const [room, setRoom] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/exams/slots", {
          body: {
            course_offering_id: offering,
            starts_at: bakuInputToIso(starts),
            ends_at: bakuInputToIso(ends),
            room_code: room.trim() || null,
          },
        }),
      ),
    onSuccess: () => {
      toast({ title: t("saved") });
      setStarts("");
      setEnds("");
      setRoom("");
      onSaved();
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = {};
    if (!offering) found.offering = t("offeringRequired");
    if (!starts) found.starts = t("startsRequired");
    if (!ends) found.ends = t("endsRequired");
    else if (starts && ends <= starts) found.ends = t("endsAfterStarts");
    setErrors(found);
    if (Object.keys(found).length === 0) save.mutate();
  };
  return (
    <Panel>
      <PanelBody>
        <form noValidate onSubmit={submit} className="flex max-w-2xl flex-col gap-4">
          <h2 className="text-lg font-semibold">{t("create")}</h2>
          {save.isError ? (
            <Banner tone="danger" title={t("failed")}>
              {errorMessage(save.error)}
            </Banner>
          ) : null}
          {save.data ? <Overlaps overlaps={save.data.overlaps} /> : null}
          <OfferingField
            value={offering}
            onChange={setOffering}
            error={errors.offering}
            labels={{ field: t("offering"), choose: t("offeringChoose") }}
          />
          <Field label={t("starts")} error={errors.starts} required>
            <Input
              type="datetime-local"
              value={starts}
              onChange={(e) => setStarts(e.target.value)}
            />
          </Field>
          <Field label={t("ends")} error={errors.ends} required>
            <Input type="datetime-local" value={ends} onChange={(e) => setEnds(e.target.value)} />
          </Field>
          <Field label={t("room")} helper={t("roomHelp")}>
            <Input value={room} maxLength={20} onChange={(e) => setRoom(e.target.value)} />
          </Field>
          <div>
            <Button type="submit" variant="primary" loading={save.isPending}>
              {t("add")}
            </Button>
          </div>
        </form>
      </PanelBody>
    </Panel>
  );
}

export function SlotTable({ items }: { items: ExamSlot[] }) {
  const t = useTranslations("exams.admin");
  const [editing, setEditing] = useState<ExamSlot | null>(null);
  const [removing, setRemoving] = useState<ExamSlot | null>(null);
  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("columns.course")}</TableHead>
            <TableHead>{t("columns.when")}</TableHead>
            <TableHead>{t("columns.room")}</TableHead>
            <TableHead>{t("columns.checks")}</TableHead>
            <TableHead>
              <span className="sr-only">{t("columns.actions")}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((slot) => (
            <TableRow key={slot.id}>
              <TableCell label={t("columns.course")}>{offeringLabel(slot.offering)}</TableCell>
              <TableCell label={t("columns.when")} className="tabular">
                {formatDateTimeRange(slot.starts_at, slot.ends_at)}
              </TableCell>
              <TableCell label={t("columns.room")}>{slot.room_code ?? "—"}</TableCell>
              <TableCell label={t("columns.checks")}>
                {slot.overlaps.length > 0 ? (
                  <Tag tone="warning">{t("overlapTag", { count: slot.overlaps.length })}</Tag>
                ) : (
                  <Tag tone="success">{t("noOverlap")}</Tag>
                )}
              </TableCell>
              <TableCell label={t("columns.actions")}>
                <div className="flex gap-2">
                  <Button variant="tertiary" size="dense" onClick={() => setEditing(slot)}>
                    {t("edit")}
                  </Button>
                  <Button variant="tertiary" size="dense" onClick={() => setRemoving(slot)}>
                    {t("remove")}
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {editing ? <EditDialog slot={editing} onClose={() => setEditing(null)} /> : null}
      {removing ? <RemoveDialog slot={removing} onClose={() => setRemoving(null)} /> : null}
    </>
  );
}

function EditDialog({ slot, onClose }: { slot: ExamSlot; onClose: () => void }) {
  const t = useTranslations("exams.admin");
  const api = useApi();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const [starts, setStarts] = useState(isoToBakuInput(slot.starts_at));
  const [ends, setEnds] = useState(isoToBakuInput(slot.ends_at));
  const [room, setRoom] = useState(slot.room_code ?? "");
  const [problem, setProblem] = useState<string | undefined>();
  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.PUT("/api/v1/exams/slots/{slot_id}", {
          params: { path: { slot_id: slot.id } },
          body: {
            starts_at: bakuInputToIso(starts),
            ends_at: bakuInputToIso(ends),
            room_code: room.trim() || null,
          },
        }),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["exams"] });
      onClose();
    },
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t("editTitle")}
        description={offeringLabel(slot.offering)}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="secondary">{t("cancel")}</Button>
            </DialogClose>
            <Button
              variant="primary"
              loading={save.isPending}
              onClick={() => {
                if (!starts || !ends || ends <= starts) return setProblem(t("endsAfterStarts"));
                setProblem(undefined);
                save.mutate();
              }}
            >
              {t("save")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {save.isError ? (
            <Banner tone="danger" title={t("failed")}>
              {errorMessage(save.error)}
            </Banner>
          ) : null}
          <Field label={t("starts")} required>
            <Input
              type="datetime-local"
              value={starts}
              onChange={(e) => setStarts(e.target.value)}
            />
          </Field>
          <Field label={t("ends")} error={problem} required>
            <Input type="datetime-local" value={ends} onChange={(e) => setEnds(e.target.value)} />
          </Field>
          <Field label={t("room")} helper={t("roomHelp")}>
            <Input value={room} maxLength={20} onChange={(e) => setRoom(e.target.value)} />
          </Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function RemoveDialog({ slot, onClose }: { slot: ExamSlot; onClose: () => void }) {
  const t = useTranslations("exams.admin");
  const api = useApi();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const remove = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.DELETE("/api/v1/exams/slots/{slot_id}", {
          params: { path: { slot_id: slot.id } },
        }),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["exams"] });
      onClose();
    },
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t("removeTitle")}
        description={t("removeBody", {
          course: slot.offering.subject_name,
          when: formatDateTimeRange(slot.starts_at, slot.ends_at),
        })}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="secondary">{t("cancel")}</Button>
            </DialogClose>
            <Button
              variant="destructive"
              loading={remove.isPending}
              onClick={() => remove.mutate()}
            >
              {t("remove")}
            </Button>
          </>
        }
      >
        {remove.isError ? (
          <Banner tone="danger" title={t("failed")}>
            {errorMessage(remove.error)}
          </Banner>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
