/**
 * The browser side of the chat WebSocket (§5.9, ADR 0003): one-use tickets through the same-origin API proxy,
 * reconnect with backoff, acks matched to events by id, and a fresh ticket before the access token ends.
 */

export type ServerEvent = { type: string; data: Record<string, unknown> };

/** A refusal of one client event: the stable code and its details (`retry_after_seconds`, `until`, …). */
export class SocketError extends Error {
  constructor(
    readonly code: string,
    readonly detail: Record<string, unknown> = {},
  ) {
    super(code);
    this.name = "SocketError";
  }
}

/** Ticket problems the connection cannot fix by retrying soon. */
export class TicketError extends Error {
  constructor(readonly kind: "signed_out" | "unavailable") {
    super(kind);
    this.name = "TicketError";
  }
}

export type CloseAction = "reconnect" | "reauthorize" | "fallback" | "stop";

/** What the client does after the server closed the socket (close codes of ADR 0003). */
export function closeAction(code: number): CloseAction {
  if (code === 4401) return "reauthorize";
  if (code === 4403) return "stop";
  // Redis or the ticket store is down: send through REST until a reconnect succeeds (§13.5).
  if (code === 1013) return "fallback";
  return "reconnect";
}

const BACKOFF_SECONDS = [1, 2, 4, 8, 16, 30];

/** Exponential backoff with ±25 % jitter, so many clients do not reconnect in the same instant. */
export function reconnectDelay(attempt: number, random: () => number = Math.random): number {
  const base = BACKOFF_SECONDS[Math.min(attempt, BACKOFF_SECONDS.length - 1)]! * 1000;
  return Math.round(base * (0.75 + random() * 0.5));
}

export const PING_INTERVAL_MS = 25_000;
const ACK_TIMEOUT_MS = 10_000;

export type ConnectionStatus = "connecting" | "online" | "offline" | "fallback";

type SocketLike = Pick<WebSocket, "send" | "close" | "readyState"> & {
  onopen: ((event: Event) => void) | null;
  onclose: ((event: CloseEvent) => void) | null;
  onmessage: ((event: MessageEvent) => void) | null;
  onerror: ((event: Event) => void) | null;
};

export type ConnectionOptions = {
  url: string;
  getTicket: () => Promise<string>;
  /** Called once the socket is open and before anything else is sent: subscribe, then flush the outbox. */
  onOpen: () => Promise<void>;
  onEvent: (event: ServerEvent) => void;
  onStatus: (status: ConnectionStatus) => void;
  /** The account cannot use chat (inactive) or the session is gone. */
  onStopped: (reason: "forbidden" | "signed_out") => void;
  createSocket?: (url: string) => SocketLike;
  random?: () => number;
};

type Waiting = {
  resolve: (data: Record<string, unknown>) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
};

export class ChatConnection {
  private socket: SocketLike | null = null;
  private attempt = 0;
  private counter = 0;
  private waiting = new Map<string, Waiting>();
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private stopped = false;
  private status: ConnectionStatus = "connecting";

  constructor(private readonly options: ConnectionOptions) {}

  /** The socket can carry requests: true from the open event, before the subscription has finished. */
  get isOpen(): boolean {
    return this.socket?.readyState === 1;
  }

  start(): void {
    this.stopped = false;
    globalThis.addEventListener?.("offline", this.wentOffline);
    globalThis.addEventListener?.("online", this.cameOnline);
    void this.open();
  }

  stop(): void {
    this.stopped = true;
    globalThis.removeEventListener?.("offline", this.wentOffline);
    globalThis.removeEventListener?.("online", this.cameOnline);
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.clearPing();
    this.socket?.close(1000);
    this.socket = null;
    this.failWaiting(new SocketError("chat.connection_closed"));
  }

  /*
   * The browser knows about a lost network before TCP does: the socket is closed at once, so new messages are
   * queued instead of waiting for an ack that cannot come, and the reconnect starts as soon as it is back.
   */
  private readonly wentOffline = () => {
    const socket = this.socket;
    if (!socket) return;
    this.socket = null;
    this.clearPing();
    this.failWaiting(new SocketError("chat.connection_closed"));
    socket.close(4000);
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.setStatus("offline");
  };

  private readonly cameOnline = () => {
    if (this.stopped || this.socket) return;
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.attempt = 0;
    void this.open();
  };

  /** Sends an event and resolves with its ack, or rejects with the server's typed error. */
  request(type: string, data: Record<string, unknown> = {}): Promise<Record<string, unknown>> {
    const socket = this.socket;
    if (!socket || socket.readyState !== 1) {
      return Promise.reject(new SocketError("chat.connection_closed"));
    }
    this.counter += 1;
    const id = `c${this.counter}`;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.waiting.delete(id);
        reject(new SocketError("chat.ack_timeout"));
        // No answer within 10 s: the connection is probably dead; reconnecting resends idempotently.
        this.socket?.close(4000);
      }, ACK_TIMEOUT_MS);
      this.waiting.set(id, { resolve, reject, timer });
      socket.send(JSON.stringify({ type, id, data }));
    });
  }

  /** Fire-and-forget events (typing). */
  emit(type: string, data: Record<string, unknown>): void {
    if (this.socket?.readyState === 1) this.socket.send(JSON.stringify({ type, data }));
  }

  private setStatus(status: ConnectionStatus): void {
    if (this.status === status) return;
    this.status = status;
    this.options.onStatus(status);
  }

  private async open(): Promise<void> {
    if (this.stopped) return;
    if (this.status !== "fallback") this.setStatus("connecting");
    let ticket: string;
    try {
      ticket = await this.options.getTicket();
    } catch (error) {
      if (error instanceof TicketError && error.kind === "signed_out") {
        this.stopped = true;
        this.options.onStopped("signed_out");
        return;
      }
      this.scheduleRetry(error instanceof TicketError ? "fallback" : "offline");
      return;
    }
    if (this.stopped) return;
    const separator = this.options.url.includes("?") ? "&" : "?";
    const create = this.options.createSocket ?? ((url: string) => new WebSocket(url));
    const socket = create(`${this.options.url}${separator}ticket=${encodeURIComponent(ticket)}`);
    this.socket = socket;
    let opened = false;
    socket.onopen = () => {
      opened = true;
      void this.opened();
    };
    socket.onmessage = (message) => {
      if (this.socket !== socket) return;
      try {
        this.handle(JSON.parse(String(message.data)) as ServerEvent);
      } catch {
        // Not a protocol frame; ignored.
      }
    };
    socket.onclose = (event) => {
      if (this.socket !== socket) return;
      this.socket = null;
      this.clearPing();
      this.failWaiting(new SocketError("chat.connection_closed"));
      if (this.stopped) return;
      const action = closeAction(event.code);
      if (action === "stop") {
        this.stopped = true;
        this.setStatus("offline");
        this.options.onStopped("forbidden");
        return;
      }
      if (action === "reauthorize") {
        // The ticket or token ended; the ticket request through the proxy refreshes the session first.
        this.attempt = 0;
        this.retryTimer = setTimeout(() => void this.open(), 0);
        return;
      }
      this.scheduleRetry(action === "fallback" ? "fallback" : opened ? "connecting" : "offline");
    };
  }

  private async opened(): Promise<void> {
    this.attempt = 0;
    this.pingTimer = setInterval(() => {
      this.request("ping").catch(() => undefined);
    }, PING_INTERVAL_MS);
    try {
      await this.options.onOpen();
    } catch {
      // The subscription failed (the socket closed meanwhile); onclose schedules the reconnect.
      return;
    }
    this.setStatus("online");
  }

  private handle(event: ServerEvent): void {
    if (event.type === "ack" || event.type === "error") {
      const id = typeof event.data.id === "string" ? event.data.id : null;
      const waiting = id ? this.waiting.get(id) : undefined;
      if (waiting && id) {
        clearTimeout(waiting.timer);
        this.waiting.delete(id);
        if (event.type === "ack") waiting.resolve(event.data);
        else {
          waiting.reject(
            new SocketError(
              String(event.data.code),
              (event.data.detail as Record<string, unknown>) ?? {},
            ),
          );
        }
        return;
      }
    }
    if (event.type === "auth.refresh_needed") {
      void this.refresh();
      return;
    }
    this.options.onEvent(event);
  }

  private async refresh(): Promise<void> {
    try {
      const ticket = await this.options.getTicket();
      await this.request("auth.refresh", { ticket });
    } catch {
      // Without a refresh the server ends the socket with auth.expired; the reconnect gets a new ticket.
    }
  }

  private scheduleRetry(status: ConnectionStatus): void {
    this.setStatus(status);
    const delay = reconnectDelay(this.attempt, this.options.random);
    this.attempt += 1;
    this.retryTimer = setTimeout(() => void this.open(), delay);
  }

  private clearPing(): void {
    if (this.pingTimer) clearInterval(this.pingTimer);
    this.pingTimer = null;
  }

  private failWaiting(error: Error): void {
    for (const waiting of this.waiting.values()) {
      clearTimeout(waiting.timer);
      waiting.reject(error);
    }
    this.waiting.clear();
  }
}
