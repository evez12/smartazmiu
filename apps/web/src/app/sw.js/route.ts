import { readFile } from "node:fs/promises";
import path from "node:path";

import { renderServiceWorker } from "@/lib/offline/service-worker-source";

export const dynamic = "force-dynamic";

/**
 * The service worker script. It is served from here instead of `public/` so that it carries the build id: a new
 * deploy changes its bytes, the browser installs the new worker and the page shows the update banner (D-118).
 */
export async function GET() {
  const source = await readFile(path.join(process.cwd(), "public", "sw-core.js"), "utf8");
  return new Response(
    renderServiceWorker(source, process.env.NEXT_PUBLIC_BUILD_ID ?? "development"),
    {
      headers: {
        "Content-Type": "text/javascript; charset=utf-8",
        "Cache-Control": "no-cache",
      },
    },
  );
}
