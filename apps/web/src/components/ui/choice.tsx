"use client";

import { Check, Minus } from "lucide-react";
import {
  Checkbox as CheckboxPrimitive,
  RadioGroup as RadioPrimitive,
  Switch as SwitchPrimitive,
} from "radix-ui";
import { useId, type ComponentProps, type ReactNode } from "react";

import { cn } from "@/lib/cn";

import { Icon } from "./icon";

const boxClasses = [
  "relative flex size-4 shrink-0 items-center justify-center border border-border-control bg-surface",
  "transition-colors disabled:cursor-not-allowed disabled:opacity-60 aria-invalid:border-danger",
  // 44 px touch target around the 16 px box.
  "after:absolute after:-inset-3.5 after:content-[''] pointer-fine:after:-inset-1",
].join(" ");

/** Descriptions are linked to their control, so screen readers announce them with the label. */
function descriptionId(controlId: string): string {
  return `${controlId}-description`;
}

type ChoiceLabelProps = {
  label: ReactNode;
  description?: ReactNode;
  htmlFor: string;
  disabled?: boolean;
  children: ReactNode;
};

function ChoiceRow({ label, description, htmlFor, disabled, children }: ChoiceLabelProps) {
  return (
    <div className="flex items-start gap-3">
      <div className="flex h-[22px] items-center">{children}</div>
      <div className="flex flex-col">
        <label htmlFor={htmlFor} className={cn("text-text", disabled && "text-muted")}>
          {label}
        </label>
        {description ? (
          <span id={descriptionId(htmlFor)} className="text-sm text-muted">
            {description}
          </span>
        ) : null}
      </div>
    </div>
  );
}

type CheckboxProps = ComponentProps<typeof CheckboxPrimitive.Root> & {
  label: ReactNode;
  description?: ReactNode;
};

export function Checkbox({ label, description, id, className, disabled, ...rest }: CheckboxProps) {
  const generatedId = useId();
  const controlId = id ?? generatedId;
  return (
    <ChoiceRow label={label} description={description} htmlFor={controlId} disabled={disabled}>
      <CheckboxPrimitive.Root
        id={controlId}
        disabled={disabled}
        aria-describedby={description ? descriptionId(controlId) : undefined}
        className={cn(
          boxClasses,
          "rounded-control data-[state=checked]:border-primary data-[state=checked]:bg-primary",
          "data-[state=indeterminate]:border-primary data-[state=indeterminate]:bg-primary",
          className,
        )}
        {...rest}
      >
        <CheckboxPrimitive.Indicator className="text-primary-contrast">
          <Icon icon={rest.checked === "indeterminate" ? Minus : Check} size={16} />
        </CheckboxPrimitive.Indicator>
      </CheckboxPrimitive.Root>
    </ChoiceRow>
  );
}

type RadioOption = { value: string; label: ReactNode; description?: ReactNode; disabled?: boolean };

type RadioGroupProps = Omit<ComponentProps<typeof RadioPrimitive.Root>, "children"> & {
  legend: string;
  options: RadioOption[];
};

export function RadioGroup({ legend, options, className, ...rest }: RadioGroupProps) {
  const baseId = useId();
  return (
    <fieldset className={cn("flex flex-col gap-2", className)}>
      <legend className="mb-1 font-medium text-text">{legend}</legend>
      <RadioPrimitive.Root className="flex flex-col gap-2" aria-label={legend} {...rest}>
        {options.map((option) => {
          const optionId = `${baseId}-${option.value}`;
          return (
            <ChoiceRow
              key={option.value}
              label={option.label}
              description={option.description}
              htmlFor={optionId}
              disabled={option.disabled}
            >
              <RadioPrimitive.Item
                id={optionId}
                value={option.value}
                disabled={option.disabled}
                aria-describedby={option.description ? descriptionId(optionId) : undefined}
                className={cn(boxClasses, "rounded-full data-[state=checked]:border-primary")}
              >
                <RadioPrimitive.Indicator className="size-2 rounded-full bg-primary" />
              </RadioPrimitive.Item>
            </ChoiceRow>
          );
        })}
      </RadioPrimitive.Root>
    </fieldset>
  );
}

type SwitchProps = ComponentProps<typeof SwitchPrimitive.Root> & {
  label: ReactNode;
  description?: ReactNode;
};

/** Rectangular on/off switch: the 4 px control radius applies here too (§12.2). */
export function Switch({ label, description, id, className, disabled, ...rest }: SwitchProps) {
  const generatedId = useId();
  const controlId = id ?? generatedId;
  return (
    <ChoiceRow label={label} description={description} htmlFor={controlId} disabled={disabled}>
      <SwitchPrimitive.Root
        id={controlId}
        disabled={disabled}
        aria-describedby={description ? descriptionId(controlId) : undefined}
        className={cn(
          "relative inline-flex h-5 w-9 shrink-0 items-center rounded-control border border-border-control bg-bg-subtle p-0.5",
          "transition-colors disabled:cursor-not-allowed disabled:opacity-60",
          "data-[state=checked]:border-primary data-[state=checked]:bg-primary",
          "after:absolute after:-inset-3 after:content-[''] pointer-fine:after:hidden",
          className,
        )}
        {...rest}
      >
        <SwitchPrimitive.Thumb
          className={cn(
            "block size-3.5 rounded-[2px] bg-border-control transition-transform",
            "data-[state=checked]:translate-x-4 data-[state=checked]:bg-primary-contrast",
          )}
        />
      </SwitchPrimitive.Root>
    </ChoiceRow>
  );
}
