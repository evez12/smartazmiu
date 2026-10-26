import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ChatConnection,
  closeAction,
  reconnectDelay,
  SocketError,
  TicketError,
  type ConnectionOptions,
  type ConnectionStatus,
} from "./socket";

class FakeSocket {
  readyState: WebSocket["readyState"] = 0;
  sent: Array<{ type: string; id?: string; data: Record<string, unknown> }> = [];
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(readonly url: string) {}

  send(raw: string) {
    this.sent.push(JSON.parse(raw));
  }

  close(code = 1000) {
    this.readyState = 3;
    this.onclose?.({ code } as CloseEvent);
  }

  open() {
    this.readyState = 1;
    this.onopen?.(new Event("open"));
  }

  receive(type: string, data: Record<string, unknown>) {
    this.onmessage?.({ data: JSON.stringify({ type, data }) } as MessageEvent);
  }
}

function setup(overrides: Partial<ConnectionOptions> = {}) {
  const sockets: FakeSocket[] = [];
  const statuses: ConnectionStatus[] = [];
  const events: unknown[] = [];
  const stopped: string[] = [];
  let ticketNumber = 0;
  const options: ConnectionOptions = {
    url: "ws://localhost/ws",
    getTicket: vi.fn(async () => `ticket-${++ticketNumber}`),
    onOpen: vi.fn(async () => undefined),
    onEvent: (event) => events.push(event),
    onStatus: (status) => statuses.push(status),
    onStopped: (reason) => stopped.push(reason),
    createSocket: (url) => {
      const socket = new FakeSocket(url);
      sockets.push(socket);
      return socket;
    },
    random: () => 0.5,
    ...overrides,
  };
  const connection = new ChatConnection(options);
  return { connection, sockets, statuses, events, stopped, options };
}

async function flush() {
  for (let index = 0; index < 5; index++) await Promise.resolve();
}

describe("close codes and backoff", () => {
  it("maps the ADR 0003 close codes to what the client does", () => {
    expect(closeAction(4401)).toBe("reauthorize");
    expect(closeAction(4403)).toBe("stop");
    expect(closeAction(1013)).toBe("fallback");
    for (const code of [4408, 4429, 1001, 1006]) expect(closeAction(code)).toBe("reconnect");
  });

  it("backs off exponentially up to 30 s with jitter", () => {
    expect(reconnectDelay(0, () => 0.5)).toBe(1000);
    expect(reconnectDelay(3, () => 0.5)).toBe(8000);
    expect(reconnectDelay(20, () => 0.5)).toBe(30000);
    expect(reconnectDelay(0, () => 0)).toBe(750);
    expect(reconnectDelay(0, () => 1)).toBe(1250);
  });
});

describe("ChatConnection", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("opens with a ticket, subscribes, and matches acks and errors to requests", async () => {
    const { connection, sockets, statuses, events, options } = setup();
    connection.start();
    await flush();
    expect(sockets[0]!.url).toBe("ws://localhost/ws?ticket=ticket-1");
    sockets[0]!.open();
    await flush();
    expect(options.onOpen).toHaveBeenCalledOnce();
    expect(statuses).toEqual(["online"]);

    const sent = connection.request("message.send", { body: "Salam" });
    const id = sockets[0]!.sent[0]!.id;
    sockets[0]!.receive("ack", { id, message_id: "42" });
    await expect(sent).resolves.toMatchObject({ message_id: "42" });

    const refused = connection.request("message.send", { body: "x" });
    const refusedId = sockets[0]!.sent[1]!.id;
    sockets[0]!.receive("error", {
      id: refusedId,
      code: "chat.rate_limited",
      detail: { retry_after_seconds: 4 },
    });
    await expect(refused).rejects.toEqual(
      new SocketError("chat.rate_limited", { retry_after_seconds: 4 }),
    );

    sockets[0]!.receive("message.created", { id: "43" });
    expect(events).toEqual([{ type: "message.created", data: { id: "43" } }]);
    connection.stop();
  });

  it("reconnects with backoff after a drop and fails requests that were waiting", async () => {
    const { connection, sockets, statuses } = setup();
    connection.start();
    await flush();
    sockets[0]!.open();
    await flush();
    const waiting = connection.request("ping");
    sockets[0]!.close(1006);
    await expect(waiting).rejects.toMatchObject({ code: "chat.connection_closed" });
    expect(statuses.at(-1)).toBe("connecting");
    await vi.advanceTimersByTimeAsync(999);
    expect(sockets).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(sockets).toHaveLength(2);
    expect(sockets[1]!.url).toContain("ticket-2");
    connection.stop();
  });

  it("gets a new ticket at once when the authorisation ended (4401)", async () => {
    const { connection, sockets } = setup();
    connection.start();
    await flush();
    sockets[0]!.open();
    await flush();
    sockets[0]!.close(4401);
    await vi.advanceTimersByTimeAsync(0);
    expect(sockets).toHaveLength(2);
    connection.stop();
  });

  it("stops for an inactive account and when signed out", async () => {
    const forbidden = setup();
    forbidden.connection.start();
    await flush();
    forbidden.sockets[0]!.open();
    await flush();
    forbidden.sockets[0]!.close(4403);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(forbidden.sockets).toHaveLength(1);
    expect(forbidden.stopped).toEqual(["forbidden"]);

    const signedOut = setup({
      getTicket: async () => {
        throw new TicketError("signed_out");
      },
    });
    signedOut.connection.start();
    await flush();
    expect(signedOut.sockets).toHaveLength(0);
    expect(signedOut.stopped).toEqual(["signed_out"]);
  });

  it("falls back to REST while the server has no live connection (1013) and keeps trying", async () => {
    const { connection, sockets, statuses } = setup();
    connection.start();
    await flush();
    sockets[0]!.open();
    await flush();
    sockets[0]!.close(1013);
    expect(statuses.at(-1)).toBe("fallback");
    await vi.advanceTimersByTimeAsync(1000);
    expect(sockets).toHaveLength(2);
    // Still in fallback until the new socket is open and subscribed.
    expect(statuses.at(-1)).toBe("fallback");
    sockets[1]!.open();
    await flush();
    expect(statuses.at(-1)).toBe("online");
    connection.stop();
  });

  it("refreshes the ticket when the server asks before the token ends", async () => {
    const { connection, sockets, options } = setup();
    connection.start();
    await flush();
    sockets[0]!.open();
    await flush();
    sockets[0]!.receive("auth.refresh_needed", {});
    await flush();
    expect(options.getTicket).toHaveBeenCalledTimes(2);
    expect(sockets[0]!.sent.at(-1)).toMatchObject({
      type: "auth.refresh",
      data: { ticket: "ticket-2" },
    });
    connection.stop();
  });

  it("treats a missing ack as a dead connection", async () => {
    const { connection, sockets } = setup();
    connection.start();
    await flush();
    sockets[0]!.open();
    await flush();
    const waiting = connection.request("message.send", { body: "Salam" });
    vi.advanceTimersByTime(10_000);
    await expect(waiting).rejects.toMatchObject({ code: "chat.ack_timeout" });
    expect(sockets[0]!.readyState).toBe(3);
    connection.stop();
  });

  it("closes at once when the browser goes offline and reconnects when it is back", async () => {
    const { connection, sockets, statuses } = setup();
    connection.start();
    await flush();
    sockets[0]!.open();
    await flush();
    const waiting = connection.request("message.send", { body: "Salam" });
    globalThis.dispatchEvent(new Event("offline"));
    await expect(waiting).rejects.toMatchObject({ code: "chat.connection_closed" });
    expect(statuses.at(-1)).toBe("offline");
    await vi.advanceTimersByTimeAsync(60_000);
    expect(sockets).toHaveLength(1);
    globalThis.dispatchEvent(new Event("online"));
    await flush();
    expect(sockets).toHaveLength(2);
    connection.stop();
  });

  it("sends a ping every 25 seconds", async () => {
    const { connection, sockets } = setup();
    connection.start();
    await flush();
    sockets[0]!.open();
    await flush();
    vi.advanceTimersByTime(25_000);
    expect(sockets[0]!.sent.map((event) => event.type)).toEqual(["ping"]);
    connection.stop();
  });
});
