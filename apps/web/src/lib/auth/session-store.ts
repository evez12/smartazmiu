import "server-only";

import { createClient } from "redis";

import { env } from "@/lib/env";

/** Server-side session state; the browser only holds the opaque id (DECISIONS D-037). */
export type StoredSession = {
  refreshToken: string;
  accessToken: string;
  /** Unix seconds. */
  accessExpiresAt: number;
  subject: string;
  csrfToken: string;
};

export type SessionStore = {
  get(key: string): Promise<StoredSession | null>;
  set(key: string, session: StoredSession, ttlSeconds: number): Promise<void>;
  delete(key: string): Promise<void>;
};

/** The three commands the store needs. */
type RedisConnection = {
  get(key: string): Promise<string | null>;
  set(key: string, value: string, options: { EX: number }): Promise<unknown>;
  del(key: string): Promise<unknown>;
};
let client: Promise<RedisConnection> | undefined;

/** Connected on first use, so pages without a session cookie never need Redis. */
function redis(): Promise<RedisConnection> {
  if (!client) {
    const instance = createClient({
      url: env.sessionRedisUrl,
      socket: {
        connectTimeout: 3000,
        reconnectStrategy: (retries) => Math.min(retries * 200, 2000),
      },
    });
    instance.on("error", (error: unknown) =>
      console.warn(JSON.stringify({ event: "session_store_error", error: String(error) })),
    );
    client = instance.connect().then(
      (connected): RedisConnection => connected,
      (error: unknown) => {
        // The next request tries again instead of keeping a failed connection forever.
        client = undefined;
        throw error;
      },
    );
  }
  return client;
}

const PREFIX = "web:session:";

const redisStore: SessionStore = {
  async get(key) {
    const value = await (await redis()).get(PREFIX + key);
    return value ? (JSON.parse(value) as StoredSession) : null;
  },
  async set(key, session, ttlSeconds) {
    await (await redis()).set(PREFIX + key, JSON.stringify(session), { EX: ttlSeconds });
  },
  async delete(key) {
    await (await redis()).del(PREFIX + key);
  },
};

export function sessionStore(): SessionStore {
  return redisStore;
}
