import { cn } from "@/lib/cn";

/**
 * Neutral text wordmark until the university supplies official assets (§12.11). Swap this component
 * (and the generated icons) to rebrand; it must never imitate the AzMİU logo or coat of arms.
 */
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("text-md font-semibold whitespace-nowrap text-primary", className)}>
      SmartAzMİU
    </span>
  );
}
