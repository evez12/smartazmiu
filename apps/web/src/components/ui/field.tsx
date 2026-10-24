"use client";

import { ChevronDown } from "lucide-react";
import { useTranslations } from "next-intl";
import { createContext, useContext, useId, type ComponentProps, type ReactNode } from "react";

import { cn } from "@/lib/cn";

import { Icon } from "./icon";

type FieldControl = {
  id: string;
  describedBy: string | undefined;
  invalid: boolean;
  required: boolean;
};

const FieldContext = createContext<FieldControl | null>(null);

/** Wires a control to its label, helper and error text. Controls also work standalone with explicit props. */
export function useFieldControl(): FieldControl | null {
  return useContext(FieldContext);
}

type FieldProps = {
  label: string;
  helper?: string;
  /** Inline validation message in plain Azerbaijani that says what to do (§12.4). */
  error?: string;
  required?: boolean;
  className?: string;
  children: ReactNode;
};

export function Field({ label, helper, error, required = false, className, children }: FieldProps) {
  const t = useTranslations("ui");
  const id = useId();
  const helperId = helper ? `${id}-helper` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [errorId, helperId].filter(Boolean).join(" ") || undefined;

  return (
    <FieldContext value={{ id, describedBy, invalid: Boolean(error), required }}>
      <div className={cn("flex flex-col gap-1", className)}>
        <label htmlFor={id} className="font-medium text-text">
          {label}
          {required ? (
            <>
              <span aria-hidden="true" className="ml-1 text-danger">
                *
              </span>
              <span className="sr-only">({t("required")})</span>
            </>
          ) : null}
        </label>
        {children}
        {error ? (
          <p id={errorId} className="text-sm text-danger">
            {error}
          </p>
        ) : null}
        {helper ? (
          <p id={helperId} className="text-sm text-muted">
            {helper}
          </p>
        ) : null}
      </div>
    </FieldContext>
  );
}

const controlClasses = [
  "w-full rounded-control border border-border-control bg-surface px-3 text-base text-text",
  "transition-colors hover:border-muted aria-invalid:border-danger",
  "disabled:cursor-not-allowed disabled:border-border-strong disabled:bg-bg-subtle disabled:text-muted",
  "read-only:border-dashed read-only:bg-bg-subtle",
].join(" ");

function useControlProps(props: {
  id?: string;
  "aria-describedby"?: string;
  "aria-invalid"?: ComponentProps<"input">["aria-invalid"];
  required?: boolean;
}) {
  const field = useFieldControl();
  return {
    id: props.id ?? field?.id,
    "aria-describedby": props["aria-describedby"] ?? field?.describedBy,
    "aria-invalid": props["aria-invalid"] ?? (field?.invalid || undefined),
    required: props.required ?? field?.required,
  };
}

export function Input({ className, ...rest }: ComponentProps<"input">) {
  return (
    <input className={cn(controlClasses, "h-9", className)} {...rest} {...useControlProps(rest)} />
  );
}

export function Textarea({ className, rows = 4, ...rest }: ComponentProps<"textarea">) {
  return (
    <textarea
      rows={rows}
      className={cn(controlClasses, "min-h-20 py-2", className)}
      {...rest}
      {...useControlProps(rest)}
    />
  );
}

/** Native select: accessible and mobile-friendly; styled to match the other controls. */
export function Select({ className, children, ...rest }: ComponentProps<"select">) {
  return (
    <div className="relative">
      <select
        className={cn(controlClasses, "h-9 appearance-none pr-9", className)}
        {...rest}
        {...useControlProps(rest)}
      >
        {children}
      </select>
      <Icon
        icon={ChevronDown}
        className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-muted"
      />
    </div>
  );
}
