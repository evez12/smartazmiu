"use client";

import { CircleAlert, CircleCheck, Info, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { Toast as ToastPrimitive } from "radix-ui";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { cn } from "@/lib/cn";

import { Icon } from "./icon";

/** Toasts are for transient confirmations only and never stay longer than 4 s (§12.4). */
export const TOAST_DURATION_MS = 4000;

export type ToastTone = "success" | "info" | "danger";

type ToastMessage = { id: number; title: string; description?: string; tone: ToastTone };

type ToastInput = Omit<ToastMessage, "id" | "tone"> & { tone?: ToastTone };

const ToastContext = createContext<((toast: ToastInput) => void) | null>(null);

export function useToast(): (toast: ToastInput) => void {
  const show = useContext(ToastContext);
  if (!show) throw new Error("useToast must be used inside <ToastProvider>");
  return show;
}

const toneIcon = {
  success: { icon: CircleCheck, className: "text-success" },
  info: { icon: Info, className: "text-info" },
  danger: { icon: CircleAlert, className: "text-danger" },
} as const;

let nextToastId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const t = useTranslations("ui");
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const show = useCallback((toast: ToastInput) => {
    nextToastId += 1;
    setToasts((current) => [...current, { tone: "success", ...toast, id: nextToastId }]);
  }, []);
  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);
  const value = useMemo(() => show, [show]);

  return (
    <ToastContext value={value}>
      <ToastPrimitive.Provider duration={TOAST_DURATION_MS} label={t("notifications")}>
        {children}
        {toasts.map((toast) => {
          const { icon, className } = toneIcon[toast.tone];
          return (
            <ToastPrimitive.Root
              key={toast.id}
              type={toast.tone === "danger" ? "foreground" : "background"}
              onOpenChange={(open) => {
                if (!open) dismiss(toast.id);
              }}
              className={cn(
                "flex items-start gap-3 rounded-panel border border-border bg-surface p-3 text-text shadow-overlay",
                "transition-[opacity,translate] data-[state=closed]:opacity-0 data-[swipe=end]:translate-x-full",
              )}
            >
              <Icon icon={icon} size={20} className={cn("mt-px", className)} />
              <div className="flex min-w-0 flex-1 flex-col">
                <ToastPrimitive.Title className="font-medium">{toast.title}</ToastPrimitive.Title>
                {toast.description ? (
                  <ToastPrimitive.Description className="text-muted">
                    {toast.description}
                  </ToastPrimitive.Description>
                ) : null}
              </div>
              <ToastPrimitive.Close
                aria-label={t("close")}
                className="rounded-control p-1 text-muted hover:text-text"
              >
                <Icon icon={X} />
              </ToastPrimitive.Close>
            </ToastPrimitive.Root>
          );
        })}
        <ToastPrimitive.Viewport className="fixed right-4 bottom-20 z-[60] flex w-[calc(100vw-32px)] max-w-sm flex-col gap-2 outline-none md:bottom-4" />
      </ToastPrimitive.Provider>
    </ToastContext>
  );
}
