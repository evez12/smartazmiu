"use client";

import { ChevronDown, Paperclip } from "lucide-react";
import { useTranslations } from "next-intl";
import { createContext, useContext, useId, type ComponentProps, type ReactNode } from "react";

import { cn } from "@/lib/cn";

import { buttonVariants } from "./button";
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
  // The attribute, not `:read-only`: browsers also match <select> and file inputs with the pseudo-class.
  "[&[readonly]]:border-dashed [&[readonly]]:bg-bg-subtle",
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

type FileInputProps = Omit<ComponentProps<"input">, "type" | "value" | "onChange"> & {
  file: File | null;
  onFileChange: (file: File | null) => void;
};

/**
 * File picker with Azerbaijani labels: the browser's own button text follows the browser language (§12.8).
 * The real input stays focusable and labelled by the surrounding Field.
 */
export function FileInput({ file, onFileChange, className, ...rest }: FileInputProps) {
  const t = useTranslations("ui");
  const control = useControlProps(rest);
  return (
    <div className={cn("flex min-h-9 flex-wrap items-center gap-x-3 gap-y-1", className)}>
      <label
        className={cn(
          buttonVariants({ variant: "secondary", size: "dense" }),
          "cursor-pointer has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus",
        )}
      >
        <Icon icon={Paperclip} />
        {t("chooseFile")}
        <input
          type="file"
          className="sr-only"
          onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
          {...rest}
          {...control}
        />
      </label>
      <span className={cn("min-w-0 break-all", file ? "text-text" : "text-muted")}>
        {file ? file.name : t("noFileChosen")}
      </span>
    </div>
  );
}
