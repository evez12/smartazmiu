import { encode } from "uqr";

/**
 * The ticket code as a QR symbol: one SVG path of dark modules on a light quiet zone. Colours come from the
 * `--qr-*` tokens, which stay dark-on-light in the dark theme because inverted codes fail on many scanners.
 */
export function TicketQr({ code, label }: { code: string; label: string }) {
  const { size, data } = encode(code, { ecc: "M", border: 4 });
  let path = "";
  data.forEach((row, y) =>
    row.forEach((dark, x) => {
      if (dark) path += `M${x} ${y}h1v1h-1z`;
    }),
  );
  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${size} ${size}`}
      shapeRendering="crispEdges"
      className="block size-56 max-w-full"
    >
      <rect width={size} height={size} fill="var(--qr-light)" />
      <path d={path} fill="var(--qr-dark)" />
    </svg>
  );
}
