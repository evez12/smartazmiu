"use client";

import { Check, X } from "lucide-react";
import { useTranslations } from "next-intl";
import {
  Dialog as DialogPrimitive,
  DropdownMenu as MenuPrimitive,
  Tooltip as TooltipPrimitive,
} from "radix-ui";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/cn";

import { Button } from "./button";
import { Icon } from "./icon";

/** Overlays are the only elements with a shadow (§12.2) and fade in for 140 ms. */
const overlaySurface =
  "z-50 rounded-panel border border-border bg-surface text-text shadow-overlay transition-opacity data-[state=closed]:opacity-0";

// --- Tooltip ---------------------------------------------------------------------------------

export const TooltipProvider = TooltipPrimitive.Provider;

export function Tooltip({ content, children }: { content: ReactNode; children: ReactNode }) {
  return (
    <TooltipPrimitive.Root delayDuration={400}>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          sideOffset={4}
          className={cn(overlaySurface, "max-w-64 rounded-control px-2 py-1 text-sm")}
        >
          {content}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}

// --- Dropdown menu -----------------------------------------------------------------------------

export const Menu = MenuPrimitive.Root;
export const MenuTrigger = MenuPrimitive.Trigger;
export const MenuGroup = MenuPrimitive.Group;
export const MenuRadioGroup = MenuPrimitive.RadioGroup;

export function MenuContent({
  className,
  sideOffset = 4,
  align = "end",
  ...rest
}: ComponentProps<typeof MenuPrimitive.Content>) {
  return (
    <MenuPrimitive.Portal>
      <MenuPrimitive.Content
        sideOffset={sideOffset}
        align={align}
        className={cn(overlaySurface, "min-w-48 p-1", className)}
        {...rest}
      />
    </MenuPrimitive.Portal>
  );
}

const menuItemClasses =
  "relative flex min-h-9 cursor-default items-center gap-2 rounded-control px-2 outline-none select-none data-[disabled]:text-muted data-[highlighted]:bg-bg-subtle pointer-coarse:min-h-11";

export function MenuItem({
  className,
  destructive,
  ...rest
}: ComponentProps<typeof MenuPrimitive.Item> & { destructive?: boolean }) {
  return (
    <MenuPrimitive.Item
      className={cn(menuItemClasses, destructive && "text-danger", className)}
      {...rest}
    />
  );
}

export function MenuRadioItem({
  className,
  children,
  ...rest
}: ComponentProps<typeof MenuPrimitive.RadioItem>) {
  return (
    <MenuPrimitive.RadioItem className={cn(menuItemClasses, "pl-8", className)} {...rest}>
      <MenuPrimitive.ItemIndicator className="absolute left-2 flex items-center">
        <Icon icon={Check} />
      </MenuPrimitive.ItemIndicator>
      {children}
    </MenuPrimitive.RadioItem>
  );
}

export function MenuLabel({ className, ...rest }: ComponentProps<typeof MenuPrimitive.Label>) {
  return (
    <MenuPrimitive.Label className={cn("px-2 py-1 text-sm text-muted", className)} {...rest} />
  );
}

export function MenuSeparator({ className }: { className?: string }) {
  return <MenuPrimitive.Separator className={cn("-mx-1 my-1 h-px bg-border", className)} />;
}

// --- Dialog and sheet ----------------------------------------------------------------------------

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

function Backdrop() {
  // A plain dimmed layer: no blur (§12.10).
  return (
    <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-backdrop transition-opacity data-[state=closed]:opacity-0" />
  );
}

type DialogContentProps = ComponentProps<typeof DialogPrimitive.Content> & {
  title: string;
  description?: ReactNode;
  footer?: ReactNode;
};

export function DialogContent({
  title,
  description,
  footer,
  className,
  children,
  ...rest
}: DialogContentProps) {
  const t = useTranslations("ui");
  return (
    <DialogPrimitive.Portal>
      <Backdrop />
      <DialogPrimitive.Content
        className={cn(
          overlaySurface,
          "fixed top-1/2 left-1/2 flex max-h-[calc(100dvh-32px)] w-[calc(100vw-32px)] max-w-lg -translate-x-1/2 -translate-y-1/2 flex-col",
          className,
        )}
        {...rest}
      >
        <header className="flex items-start justify-between gap-4 border-b border-border px-6 py-4">
          <div className="flex flex-col gap-1">
            <DialogPrimitive.Title className="text-lg font-semibold">{title}</DialogPrimitive.Title>
            {description ? (
              <DialogPrimitive.Description className="text-muted">
                {description}
              </DialogPrimitive.Description>
            ) : null}
          </div>
          <DialogPrimitive.Close asChild>
            <Button variant="tertiary" size="icon-dense" aria-label={t("close")}>
              <Icon icon={X} />
            </Button>
          </DialogPrimitive.Close>
        </header>
        {children ? <div className="overflow-y-auto px-6 py-4">{children}</div> : null}
        {footer ? (
          <footer className="flex flex-wrap justify-end gap-2 border-t border-border px-6 py-4">
            {footer}
          </footer>
        ) : null}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

type ConfirmDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** States exactly what will happen, e.g. which data is removed (§12.4). */
  consequence: string;
  confirmLabel: string;
  onConfirm: () => void;
  destructive?: boolean;
  pending?: boolean;
};

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  consequence,
  confirmLabel,
  onConfirm,
  destructive = false,
  pending = false,
}: ConfirmDialogProps) {
  const t = useTranslations("ui");
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={title}
        description={consequence}
        role="alertdialog"
        footer={
          <>
            <DialogClose asChild>
              <Button variant="secondary">{t("cancel")}</Button>
            </DialogClose>
            <Button
              variant={destructive ? "destructive-solid" : "primary"}
              loading={pending}
              onClick={onConfirm}
            >
              {confirmLabel}
            </Button>
          </>
        }
      />
    </Dialog>
  );
}

type SheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  side?: "left" | "bottom";
  children: ReactNode;
};

/** Side or bottom panel; the mobile navigation uses it (§12.6). */
export function Sheet({ open, onOpenChange, title, side = "left", children }: SheetProps) {
  const t = useTranslations("ui");
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <Backdrop />
        <DialogPrimitive.Content
          className={cn(
            "fixed z-50 flex flex-col border-border bg-surface text-text shadow-overlay transition-[opacity,translate]",
            side === "left"
              ? "inset-y-0 left-0 w-72 max-w-[85vw] border-r data-[state=closed]:-translate-x-4 data-[state=closed]:opacity-0"
              : "inset-x-0 bottom-0 max-h-[85dvh] rounded-t-panel border-t pb-[env(safe-area-inset-bottom)] data-[state=closed]:translate-y-4 data-[state=closed]:opacity-0",
          )}
          aria-describedby={undefined}
        >
          <header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-4">
            <DialogPrimitive.Title className="font-semibold">{title}</DialogPrimitive.Title>
            <DialogPrimitive.Close asChild>
              <Button variant="tertiary" size="icon" aria-label={t("close")}>
                <Icon icon={X} size={20} />
              </Button>
            </DialogPrimitive.Close>
          </header>
          <div className="flex-1 overflow-y-auto">{children}</div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </Dialog>
  );
}
