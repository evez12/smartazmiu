"use client";

import type { VariantProps } from "class-variance-authority";
import { LoaderCircle } from "lucide-react";
import { Slot } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "@/lib/cn";

import { buttonVariants } from "./button-variants";
import { Icon } from "./icon";
import { useOfflineLock, type NetworkNeed } from "./network";

type ButtonProps = ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
    /** In-place action running: keeps the label, shows a spinner and blocks repeat submits. */
    loading?: boolean;
    /** Whether the button needs the server; see `networkDefault`. */
    network?: NetworkNeed;
  };

/**
 * What a button is when it does not say. Buttons that send a form, are the page's main or a destructive action, or
 * show a running action (`loading` is passed) talk to the server and are switched off while offline (§13.6). A
 * button that works on the page alone says `network="local"`; a secondary or tertiary one that calls the server
 * says `network="required"`.
 */
export function networkDefault(
  props: Pick<ButtonProps, "type" | "variant" | "loading">,
): NetworkNeed {
  const strong =
    props.variant === "primary" ||
    props.variant === "destructive" ||
    props.variant === "destructive-solid";
  return props.type === "submit" || strong || props.loading !== undefined ? "required" : "local";
}

export function Button({
  className,
  variant,
  size,
  asChild = false,
  loading,
  disabled,
  children,
  type,
  network,
  ...rest
}: ButtonProps) {
  const classes = cn(buttonVariants({ variant, size }), className);
  const lock = useOfflineLock(network ?? networkDefault({ type, variant, loading }));
  if (asChild) {
    return (
      <Slot.Root className={classes} {...rest}>
        {children}
      </Slot.Root>
    );
  }
  const busy = loading === true;
  return (
    <button
      type={type ?? "button"}
      className={classes}
      disabled={disabled || busy || lock.locked}
      aria-busy={busy || undefined}
      {...lock.props}
      {...rest}
    >
      {busy ? <Icon icon={LoaderCircle} className="animate-spin" /> : null}
      {children}
    </button>
  );
}
