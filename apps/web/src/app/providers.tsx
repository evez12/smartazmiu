"use client";

import { ThemeProvider } from "next-themes";
import type { ReactNode } from "react";

import { NetworkProvider } from "@/components/ui/network";
import { ToastProvider } from "@/components/ui/toast";
import { TooltipProvider } from "@/components/ui/overlay";

export function Providers({ nonce, children }: { nonce?: string; children: ReactNode }) {
  return (
    <ThemeProvider
      attribute="data-theme"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
      nonce={nonce}
    >
      <TooltipProvider>
        <NetworkProvider>
          <ToastProvider>{children}</ToastProvider>
        </NetworkProvider>
      </TooltipProvider>
    </ThemeProvider>
  );
}
