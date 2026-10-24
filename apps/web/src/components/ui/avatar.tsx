import { Avatar as AvatarPrimitive } from "radix-ui";

import { cn } from "@/lib/cn";

const sizes = { 24: "size-6 text-xs", 32: "size-8 text-sm", 40: "size-10 text-base" } as const;

/** Initials using Azerbaijani case rules, so "ilkin" becomes "İ" rather than "I". */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = parts.length > 1 ? [parts[0], parts[parts.length - 1]] : parts.slice(0, 1);
  return letters.map((part) => Array.from(part ?? "")[0]?.toLocaleUpperCase("az") ?? "").join("");
}

type AvatarProps = {
  name: string;
  src?: string;
  size?: keyof typeof sizes;
  /** Set when the name is already shown next to the avatar, so screen readers do not hear it twice. */
  decorative?: boolean;
  className?: string;
};

export function Avatar({ name, src, size = 32, decorative = false, className }: AvatarProps) {
  return (
    <AvatarPrimitive.Root
      className={cn(
        "inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full border border-border bg-bg-subtle font-medium text-text select-none",
        sizes[size],
        className,
      )}
    >
      {src ? <AvatarPrimitive.Image src={src} alt="" className="size-full object-cover" /> : null}
      <AvatarPrimitive.Fallback aria-hidden="true">{initials(name)}</AvatarPrimitive.Fallback>
      {decorative ? null : <span className="sr-only">{name}</span>}
    </AvatarPrimitive.Root>
  );
}
