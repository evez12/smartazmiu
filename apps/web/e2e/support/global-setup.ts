import http from "node:http";
import https from "node:https";

import { countDifferences, seedRowCounts } from "./database";

/** One GET of `/healthz`; resolves with the status, or rejects when the connection fails (for example a reset). */
function probe(base: URL): Promise<number> {
  const client = base.protocol === "https:" ? https : http;
  return new Promise((resolve, reject) => {
    const request = client.get(
      new URL("/healthz", base),
      { rejectUnauthorized: process.env.E2E_IGNORE_HTTPS_ERRORS !== "1", timeout: 5000 },
      (response) => {
        response.resume();
        resolve(response.statusCode ?? 0);
      },
    );
    request.on("timeout", () => request.destroy(new Error("timeout")));
    request.on("error", reject);
  });
}

/**
 * Right after `make up` the first connections from the host can be reset by Docker Desktop's port forwarding before
 * nginx sees them (seen on 2026-11-03: `ERR_CONNECTION_RESET` on the first test's first request, nothing in the nginx
 * log). Waiting for the stack to answer is a readiness check, not a retry of a test.
 */
async function waitUntilReachable(): Promise<void> {
  if (!process.env.E2E_BASE_URL) return;
  const base = new URL(process.env.E2E_BASE_URL);
  const deadline = Date.now() + 60_000;
  for (;;) {
    try {
      if ((await probe(base)) === 200) return;
    } catch {
      // not ready yet
    }
    if (Date.now() > deadline) throw new Error(`${base.origin} did not answer within 60 s`);
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

/**
 * Data hygiene check: the suite starts on the seeded sample data (`make e2e` runs `make seed` first) and must
 * leave every seed table with the row count it found. A test that imports records removes them itself
 * (`TestRecords`); this check catches the ones that forget.
 */
export default async function globalSetup() {
  await waitUntilReachable();
  // The screenshot comparison (`make visual`) runs in a container without the stack's database.
  if (process.env.E2E_DATA_CHECK === "off") return;
  const before = await seedRowCounts();
  return async () => {
    const differences = countDifferences(before, await seedRowCounts());
    if (differences.length) {
      throw new Error(`E2E run left seed data changed:\n  ${differences.join("\n  ")}`);
    }
  };
}
