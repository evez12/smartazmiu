import type { LucideIcon, LucideProps } from "lucide-react";

import { cn } from "@/lib/cn";

export type IconSize = 16 | 20;

type IconProps = Omit<LucideProps, "size" | "strokeWidth" | "absoluteStrokeWidth"> & {
  icon: LucideIcon;
  size?: IconSize;
  /** Accessible name; omit for decorative icons next to visible text. */
  label?: string;
};

/** The only way feature code renders an icon: Lucide, 16/20 px, 1.5 px stroke at every size (§12.4). */
export function Icon({ icon: Glyph, size = 16, label, className, ...rest }: IconProps) {
  return (
    <Glyph
      size={size}
      strokeWidth={1.5}
      absoluteStrokeWidth
      focusable="false"
      aria-hidden={label ? undefined : true}
      aria-label={label}
      role={label ? "img" : undefined}
      className={cn("shrink-0", className)}
      {...rest}
    />
  );
}
