/**
 * Grows the tap area of a small control to at least 44 × 44 px on touch screens without changing how it looks
 * (§12.6, WCAG 2.5.8). It is centred on the control and sized in pixels, so it does not depend on the root font
 * size. Mouse users get nothing extra; the control needs a containing block, hence `relative`.
 */
export const touchTarget = [
  "relative after:absolute after:top-1/2 after:left-1/2 after:size-full after:min-h-[44px] after:min-w-[44px]",
  "after:-translate-x-1/2 after:-translate-y-1/2 after:content-[''] pointer-fine:after:hidden",
].join(" ");
