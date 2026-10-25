"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useDeferredValue, useState } from "react";

import { Button } from "@/components/ui/button";
import { RadioGroup } from "@/components/ui/choice";
import { Field, Input, Select } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";

import { AUDIENCE_TYPES, type AudienceOption, type AudienceType } from "./model";

export type AudienceChoice = { type: AudienceType; target: AudienceOption | null };

type AudiencePickerProps = {
  value: AudienceChoice;
  onChange: (value: AudienceChoice) => void;
  /** Shown under the choice after a submit attempt without a target. */
  error?: string;
};

/** Who an announcement or event is for: the whole university, or one faculty, specialty, group or offering. */
export function AudiencePicker({ value, onChange, error }: AudiencePickerProps) {
  const t = useTranslations("audiences");
  const api = useApi();
  const [query, setQuery] = useState("");
  const search = useDeferredValue(query.trim());

  const options = useQuery({
    queryKey: ["audiences", value.type, search],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/audiences/options", {
          params: { query: { type: value.type, q: search } },
        }),
      ).items,
    enabled: value.type !== "university",
  });
  // The chosen target stays listed while the search shows other results.
  const listed = options.data ?? [];
  const choices =
    value.target && !listed.some((option) => option.id === value.target!.id)
      ? [value.target, ...listed]
      : listed;

  return (
    <div className="flex flex-col gap-4">
      <Field label={t("typeLabel")} required>
        <Select
          value={value.type}
          onChange={(event) => {
            setQuery("");
            onChange({ type: event.target.value as AudienceType, target: null });
          }}
        >
          {AUDIENCE_TYPES.map((type) => (
            <option key={type} value={type}>
              {t(`types.${type}`)}
            </option>
          ))}
        </Select>
      </Field>

      {value.type === "university" ? (
        <p className="text-sm text-muted">{t("universityHint")}</p>
      ) : (
        <div className="flex flex-col gap-3">
          <Field label={t("search")} helper={t("searchHelp")}>
            <Input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              autoComplete="off"
            />
          </Field>
          {options.isPending ? (
            <div className="flex flex-col gap-2" aria-busy="true">
              <Skeleton className="h-5 w-64" />
              <Skeleton className="h-5 w-56" />
              <Skeleton className="h-5 w-60" />
            </div>
          ) : options.isError ? (
            <div className="flex flex-col items-start gap-2">
              <p className="text-sm text-danger">{t("failed")}</p>
              <Button size="dense" onClick={() => options.refetch()}>
                {t("retry")}
              </Button>
            </div>
          ) : choices.length === 0 ? (
            <p className="text-sm text-muted">{t("none")}</p>
          ) : (
            <div className="max-h-72 overflow-y-auto rounded-control border border-border p-3">
              <RadioGroup
                legend={t(`types.${value.type}`)}
                value={value.target?.id ?? ""}
                onValueChange={(id) =>
                  onChange({
                    type: value.type,
                    target: choices.find((option) => option.id === id) ?? null,
                  })
                }
                options={choices.map((option) => ({
                  value: option.id,
                  label: option.label,
                  description: option.detail || undefined,
                }))}
              />
            </div>
          )}
          {error ? (
            <p className="text-sm text-danger" role="alert">
              {error}
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}
