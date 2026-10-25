import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { ApiProvider } from "@/lib/api/provider";
import { applicationServerKey } from "@/lib/push";
import { renderWithIntl } from "@/test/render";

import { NotificationBell } from "./bell";
import { Inbox } from "./inbox";
import type { NotificationItem, NotificationSettings } from "./model";
import { PushDevice } from "./push-device";
import { NotificationSettingsForm } from "./settings-form";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh }) }));

const fetchMock = vi.fn<(request: Request) => Promise<Response>>();

beforeEach(() => vi.stubGlobal("fetch", fetchMock));
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  refresh.mockReset();
});

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderInApp(ui: ReactElement) {
  return renderWithIntl(
    <ApiProvider csrfToken="csrf-0123">
      <ToastProvider>{ui}</ToastProvider>
    </ApiProvider>,
  );
}

function notification(overrides: Partial<NotificationItem> = {}): NotificationItem {
  return {
    id: "01a17494-cd82-7333-a6fb-9b011f1ae9a7",
    category: "announcements",
    kind: "announcement.published",
    title: "Qış imtahan sessiyasının cədvəli dərc olundu",
    link: "/announcements/01a1",
    created_at: "2026-11-02T06:30:00Z",
    read_at: null,
    ...overrides,
  };
}

/** Answers by path, so the order of the bell's parallel requests does not matter. */
function routes(handlers: Record<string, () => Response>) {
  fetchMock.mockImplementation(async (request) => {
    const { pathname } = new URL(request.url);
    const key = `${request.method} ${pathname}`;
    const handler = handlers[key];
    if (!handler) throw new Error(`Unexpected request ${key}`);
    return handler();
  });
}

describe("NotificationBell", () => {
  it("shows the unread count, the latest notifications and marks one read when opened", async () => {
    routes({
      "GET /api/v1/me/notifications/unread-count": () => json({ count: 2 }),
      "GET /api/v1/me/notifications": () =>
        json({
          items: [
            notification(),
            notification({
              id: "01a17494-0000-7000-8000-000000000002",
              kind: "event.published",
              title: "Kitab sərgisi",
              created_at: "2026-11-01T09:00:00Z",
              read_at: "2026-11-01T10:00:00Z",
            }),
          ],
          next_before: null,
        }),
      "POST /api/v1/me/notifications/01a17494-cd82-7333-a6fb-9b011f1ae9a7/read": () =>
        json(notification({ read_at: "2026-11-02T07:00:00Z" })),
    });
    renderInApp(<NotificationBell />);

    const bell = await screen.findByRole("button", { name: "Bildirişlər, 2 oxunmamış" });
    await userEvent.click(bell);
    const panel = await screen.findByRole("dialog", { name: "Bildirişlər" });
    expect(await within(panel).findByText("Kitab sərgisi")).toBeInTheDocument();
    // Unread is a text tag, not colour alone (§12.2); the read one has none.
    expect(within(panel).getAllByText("Oxunmayıb")).toHaveLength(1);
    expect(within(panel).getByText("Yeni tədbir")).toBeInTheDocument();
    expect(within(panel).getByText("2 Noyabr 2026, 10:30")).toBeInTheDocument();

    await userEvent.click(within(panel).getByRole("link", { name: /Qış imtahan/ }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([request]) => request.method === "POST")).toBe(true),
    );
    const post = fetchMock.mock.calls.find(([request]) => request.method === "POST")![0];
    expect(post.headers.get("x-csrf-token")).toBe("csrf-0123");
  });

  it("explains an empty list and a failed load", async () => {
    let fail = true;
    routes({
      "GET /api/v1/me/notifications/unread-count": () => json({ count: 0 }),
      "GET /api/v1/me/notifications": () =>
        fail
          ? json({ error: { code: "server.internal_error" } }, 500)
          : json({ items: [], next_before: null }),
    });
    renderInApp(<NotificationBell />);
    await userEvent.click(await screen.findByRole("button", { name: "Bildirişlər" }));
    const panel = await screen.findByRole("dialog");
    // One automatic retry (retry: 1), then the error state with its own retry button.
    expect(
      await within(panel).findByText(
        "Bildirişləri yükləmək mümkün olmadı. Yenidən cəhd edin.",
        {},
        { timeout: 4000 },
      ),
    ).toBeInTheDocument();
    fail = false;
    await userEvent.click(within(panel).getByRole("button", { name: "Yenidən cəhd edin" }));
    expect(await within(panel).findByText(/Hələ bildirişiniz yoxdur/)).toBeInTheDocument();
  });
});

describe("Inbox", () => {
  it("loads older pages with the cursor and marks everything read", async () => {
    routes({
      "GET /api/v1/me/notifications": () =>
        json({ items: [notification({ id: "01a1-old", title: "Köhnə elan" })], next_before: null }),
      "POST /api/v1/me/notifications/read-all": () => json({ count: 0 }),
    });
    renderInApp(
      <Inbox
        firstPage={{ items: [notification()], next_before: "01a17494-cd82-7333-a6fb-9b011f1ae9a7" }}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Daha çox yükləyin" }));
    expect(await screen.findByText("Köhnə elan")).toBeInTheDocument();
    const page = fetchMock.mock.calls[0]![0];
    expect(new URL(page.url).searchParams.get("before")).toBe(
      "01a17494-cd82-7333-a6fb-9b011f1ae9a7",
    );
    expect(screen.queryByRole("button", { name: "Daha çox yükləyin" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Hamısını oxunmuş kimi qeyd edin" }));
    expect(
      await screen.findByText("Bütün bildirişlər oxunmuş kimi qeyd olundu"),
    ).toBeInTheDocument();
  });

  it("explains an empty inbox", () => {
    renderInApp(<Inbox firstPage={{ items: [], next_before: null }} />);
    expect(screen.getByText(/Hələ bildirişiniz yoxdur/)).toBeInTheDocument();
  });
});

const settings: NotificationSettings = {
  categories: [
    { category: "announcements", push: true, email: true },
    { category: "events", push: true, email: false },
    { category: "schedule", push: true, email: false },
  ],
  quiet_hours: { enabled: true, starts_at: "23:00", ends_at: "08:00" },
  push_public_key: "BOr4T0Pm",
  devices: 1,
};

describe("NotificationSettingsForm", () => {
  it("saves channels per category and quiet hours", async () => {
    fetchMock.mockResolvedValue(json(settings));
    renderInApp(<NotificationSettingsForm settings={settings} />);

    const events = screen.getByRole("group", { name: "Tədbirlər" });
    await userEvent.click(within(events).getByRole("checkbox", { name: "E-poçt" }));
    const start = screen.getByLabelText("Başlanğıc");
    await userEvent.clear(start);
    await userEvent.type(start, "22:30");
    await userEvent.click(screen.getByRole("button", { name: "Yadda saxlayın" }));

    await waitFor(() => expect(refresh).toHaveBeenCalled());
    const request = fetchMock.mock.calls[0]![0];
    expect(request.method).toBe("PUT");
    expect(await request.json()).toEqual({
      categories: [
        { category: "announcements", push: true, email: true },
        { category: "events", push: true, email: true },
        { category: "schedule", push: true, email: false },
      ],
      quiet_hours: { enabled: true, starts_at: "22:30", ends_at: "08:00" },
    });
  });

  it("refuses quiet hours that start and end at the same time", async () => {
    renderInApp(
      <NotificationSettingsForm
        settings={{
          ...settings,
          quiet_hours: { enabled: true, starts_at: "08:00", ends_at: "08:00" },
        }}
      />,
    );
    expect(screen.getByText("Başlanğıc və son vaxt fərqli olmalıdır.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yadda saxlayın" })).toBeDisabled();
  });
});

describe("PushDevice", () => {
  it("explains a browser without Web Push", async () => {
    renderInApp(<PushDevice publicKey="BOr4T0Pm" devices={0} />);
    expect(
      await screen.findByText(/Bu brauzer veb bildirişlərini dəstəkləmir/),
    ).toBeInTheDocument();
    expect(screen.getByText("Heç bir cihaz qeydiyyatda deyil.")).toBeInTheDocument();
  });

  it("explains when push is not configured", () => {
    renderInApp(<PushDevice publicKey={null} devices={2} />);
    expect(screen.getByText(/hazırda istifadəyə verilməyib/)).toBeInTheDocument();
    expect(screen.getByText("2 cihaz qeydiyyatdadır.")).toBeInTheDocument();
  });

  it("subscribes this browser and registers it with the API", async () => {
    const subscription = {
      endpoint: "https://fcm.googleapis.com/fcm/send/abc",
      toJSON: () => ({ keys: { p256dh: "BKey", auth: "Auth" } }),
    };
    const pushManager = {
      getSubscription: vi.fn(async () => null),
      subscribe: vi.fn(async () => subscription),
    };
    const registration = { pushManager };
    vi.stubGlobal("PushManager", class {});
    vi.stubGlobal(
      "Notification",
      Object.assign(class {}, {
        permission: "default",
        requestPermission: vi.fn(async () => "granted"),
      }),
    );
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: {
        getRegistration: vi.fn(async () => registration),
        register: vi.fn(async () => registration),
        ready: Promise.resolve(registration),
      },
    });
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    try {
      renderInApp(<PushDevice publicKey="AQAB" devices={0} />);
      await userEvent.click(await screen.findByRole("button", { name: "Bu brauzerdə aktiv edin" }));
      expect(await screen.findByText("Bu brauzerdə bildirişlər aktivdir.")).toBeInTheDocument();
      const request = fetchMock.mock.calls[0]![0];
      expect(request.method).toBe("PUT");
      expect(await request.json()).toEqual({
        endpoint: "https://fcm.googleapis.com/fcm/send/abc",
        keys: { p256dh: "BKey", auth: "Auth" },
      });
      expect(pushManager.subscribe).toHaveBeenCalledWith({
        userVisibleOnly: true,
        applicationServerKey: new Uint8Array([1, 0, 1]),
      });
    } finally {
      Reflect.deleteProperty(navigator, "serviceWorker");
    }
  });
});

describe("applicationServerKey", () => {
  it("decodes base64url without padding", () => {
    expect([...applicationServerKey("-_8")]).toEqual([251, 255]);
    expect([...applicationServerKey("AQAB")]).toEqual([1, 0, 1]);
  });
});
