"use client";

import { useQuery } from "@tanstack/react-query";
import { TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Field, Select } from "@/components/ui/field";
import { Panel } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { ApiRequestError, unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";

export type CourseOffering = components["schemas"]["CourseOfferingOut"];

export function offeringLabel(offering: CourseOffering): string {
  return [offering.subject_name, offering.groups.join(", "), offering.semester]
    .filter(Boolean)
    .join(" · ");
}

/** The offerings the user may add assignments and quizzes to (teachers: those they teach; staff: any). */
export function useManagedOfferings() {
  const api = useApi();
  return useQuery({
    queryKey: ["coursework-offerings"],
    queryFn: async () => unwrap(await api.GET("/api/v1/coursework/offerings")).items,
    staleTime: 5 * 60_000,
  });
}

/** The offering picker of both builders; the offerings come from the server, so nobody types an id. */
export function OfferingField({
  value,
  onChange,
  error,
  labels,
}: {
  value: string;
  onChange: (id: string) => void;
  error?: string;
  labels: { field: string; choose: string };
}) {
  const offerings = useManagedOfferings();
  return (
    <Field label={labels.field} error={error} required>
      <Select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{labels.choose}</option>
        {offerings.data?.map((offering) => (
          <option key={offering.id} value={offering.id}>
            {offeringLabel(offering)}
          </option>
        ))}
      </Select>
    </Field>
  );
}

/** Loading, forbidden, error-with-retry and empty states for a list or detail screen (§13.6). */
export function ScreenState({
  loading,
  error,
  empty,
  emptyMessage,
  emptyAction,
  errorMessage,
  retryLabel,
  retry,
}: {
  loading: boolean;
  error: unknown;
  empty: boolean;
  emptyMessage: string;
  emptyAction?: ReactNode;
  errorMessage: string;
  retryLabel: string;
  retry: () => void;
}) {
  if (loading) {
    return (
      <div className="flex flex-col gap-3" aria-busy="true">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }
  if (error) {
    if (error instanceof ApiRequestError && error.status === 403) return <ForbiddenState />;
    if (error instanceof ApiRequestError && error.status === 404) {
      return (
        <Panel>
          <EmptyState icon={TriangleAlert} message={errorMessage} />
        </Panel>
      );
    }
    return (
      <Panel>
        <EmptyState
          icon={TriangleAlert}
          message={errorMessage}
          action={<Button onClick={retry}>{retryLabel}</Button>}
        />
      </Panel>
    );
  }
  if (empty) {
    return (
      <Panel>
        <EmptyState message={emptyMessage} action={emptyAction} />
      </Panel>
    );
  }
  return null;
}

/** Points are shown with a decimal comma and without trailing zeros: "42,5" and "100". */
export function formatPoints(value: string | number): string {
  const number = Number(value);
  return (Number.isInteger(number) ? String(number) : number.toFixed(2).replace(/0+$/, "")).replace(
    ".",
    ",",
  );
}
