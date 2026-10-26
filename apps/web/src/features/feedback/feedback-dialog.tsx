"use client";

import { useMutation } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Checkbox, RadioGroup } from "@/components/ui/choice";
import { Field, Textarea } from "@/components/ui/field";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/overlay";
import { useToast } from "@/components/ui/toast";
import { unwrap } from "@/lib/api/browser";
import { useApi, useErrorMessage } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";

type Category = components["schemas"]["FeedbackIn"]["category"];

const CATEGORIES: readonly Category[] = ["problem", "suggestion", "question", "other"] as const;
const MAX_MESSAGE = 2000;

/** The pilot feedback form (D-074): seen by staff only; the current page is attached so problems can be found. */
export function FeedbackDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations("feedback");
  const api = useApi();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const pathname = usePathname();
  const [category, setCategory] = useState<Category>("problem");
  const [message, setMessage] = useState("");
  const [contactOk, setContactOk] = useState(false);
  const [missing, setMissing] = useState(false);

  const send = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/feedback", {
          body: { category, message: message.trim(), page: pathname, contact_ok: contactOk },
        }),
      ),
    onSuccess: () => {
      onOpenChange(false);
      setMessage("");
      setContactOk(false);
      toast({ title: t("sent") });
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={t("title")}
        description={t("description")}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="secondary">{t("cancel")}</Button>
            </DialogClose>
            <Button
              variant="primary"
              loading={send.isPending}
              onClick={() => {
                if (!message.trim()) {
                  setMissing(true);
                  return;
                }
                send.mutate();
              }}
            >
              {t("submit")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {send.isError ? (
            <Banner tone="danger" title={t("failed")}>
              {errorMessage(send.error)}
            </Banner>
          ) : null}
          <RadioGroup
            legend={t("categoryLegend")}
            value={category}
            onValueChange={(value) => setCategory(value as Category)}
            options={CATEGORIES.map((value) => ({ value, label: t(`categories.${value}`) }))}
          />
          <Field
            label={t("message")}
            helper={t("messageHelper", { max: MAX_MESSAGE })}
            error={missing ? t("messageRequired") : undefined}
            required
          >
            <Textarea
              value={message}
              maxLength={MAX_MESSAGE}
              rows={5}
              onChange={(event) => {
                setMessage(event.target.value);
                setMissing(false);
              }}
            />
          </Field>
          <Checkbox
            checked={contactOk}
            onCheckedChange={(checked) => setContactOk(checked === true)}
            label={t("contact")}
            description={t("contactHelper")}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Opens the form from a page (the support page); the profile menu opens the same dialog. */
export function FeedbackButton() {
  const t = useTranslations("feedback");
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>{t("action")}</Button>
      <FeedbackDialog open={open} onOpenChange={setOpen} />
    </>
  );
}
