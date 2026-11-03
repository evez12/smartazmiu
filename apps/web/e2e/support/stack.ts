import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Firefox ignores Playwright's offline switch for the service worker's own requests (D-128), so inside
 * `make e2e-pwa-browsers` (`E2E_STOP_STACK=1`) the network is taken away by stopping the TLS front of the local
 * https stack (D-133). The front, not the stack's nginx: a stopped nginx behind it would answer 502, which is an
 * HTTP response; a stopped front makes the connection itself fail.
 */
export const stopsFront = process.env.E2E_STOP_STACK === "1";

const repository = path.resolve(process.cwd(), "../..");

function compose(...args: string[]): void {
  execFileSync(
    "docker",
    [
      "compose",
      "-f",
      "docker-compose.yml",
      "-f",
      "docker-compose.tls.yml",
      "--profile",
      "app",
      ...args,
    ],
    {
      cwd: repository,
      env: { ...process.env, APP_PUBLIC_URL: "https://localhost" },
      stdio: "pipe",
    },
  );
}

export function stopFront(): void {
  compose("stop", "tls");
}

/** Starts the front again and waits until it is healthy; safe to call when it already runs. */
export function startFront(): void {
  compose("up", "-d", "--wait", "--no-deps", "tls");
}
