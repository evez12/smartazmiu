import "fake-indexeddb/auto";

import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IDBFactory } from "fake-indexeddb";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Schedule } from "@/features/schedule/model";
import { claimDevice, setOfflineEnabled } from "@/lib/offline/device";
import { isDismissed, recordVisit, shouldOffer } from "@/lib/offline/install";
import { putSnapshot, closeDatabase, readDevice } from "@/lib/offline/store";
import { SIGN_OUT_PENDING_KEY } from "@/lib/offline/policy";
import { renderWithIntl } from "@/test/render";

import type { ChannelHistory, ChannelList } from "./model";
import { InstallPrompt } from "./install-prompt";
import { OfflineBanner, PwaNotices } from "./notices";
import { OfflineApp } from "./offline-app";
import { UpdateBanner } from "./update-banner";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh: vi.fn() }),
  usePathname: () => "/offline",
}));

const USER = "01a19d28-c354-7be3-83ff-a11dbd4de9d1";
const SESSION_END = Math.floor(Date.now() / 1000) + 3600;

function setOnline(value: boolean) {
  Object.defineProperty(navigator, "onLine", { configurable: true, get: () => value });
  window.dispatchEvent(new Event(value ? "online" : "offline"));
}

function stubServiceWorker({ waiting, controller }: { waiting: boolean; controller: boolean }) {
  const worker = { state: "installed", postMessage: vi.fn(), addEventListener: vi.fn() };
  const registration = {
    waiting: waiting ? worker : null,
    installing: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    update: vi.fn(async () => undefined),
  };
  const container = {
    ready: Promise.resolve(registration),
    controller: controller ? {} : null,
    addEventListener: vi.fn(),
  };
  Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: container });
  return { worker, container };
}

beforeEach(() => {
  // jsdom has no matchMedia; the app is never "installed" in these tests.
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
  });
  globalThis.indexedDB = new IDBFactory();
  localStorage.clear();
  sessionStorage.clear();
  push.mockClear();
  setOnline(true);
});

afterEach(async () => {
  await closeDatabase();
  Reflect.deleteProperty(navigator, "serviceWorker");
  document.body.innerHTML = "";
});

describe("the update banner", () => {
  it("offers the new version and reloads only after the user asks", async () => {
    const { worker, container } = stubServiceWorker({ waiting: true, controller: true });
    renderWithIntl(<UpdateBanner />);
    expect(await screen.findByText("Yeni versiya var")).toBeInTheDocument();
    expect(worker.postMessage).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Yeniləyin" }));

    expect(worker.postMessage).toHaveBeenCalledWith({ type: "SKIP_WAITING" });
    expect(container.addEventListener).toHaveBeenCalledWith(
      "controllerchange",
      expect.any(Function),
      {
        once: true,
      },
    );
  });

  it("stays silent on the first install, when there is nothing older to replace", async () => {
    stubServiceWorker({ waiting: true, controller: false });
    renderWithIntl(<UpdateBanner />);
    await act(async () => undefined);
    expect(screen.queryByText("Yeni versiya var")).not.toBeInTheDocument();
  });

  it("never reloads while a composer has text that was not sent", async () => {
    const { worker } = stubServiceWorker({ waiting: true, controller: true });
    const field = document.createElement("textarea");
    field.setAttribute("data-composer", "");
    document.body.append(field);
    renderWithIntl(<UpdateBanner />);
    const button = await screen.findByRole("button", { name: "Yeniləyin" });
    expect(button).toBeEnabled();

    field.value = "Salam, sabah dərs var?";
    fireEvent.input(field);

    await waitFor(() => expect(button).toBeDisabled());
    expect(screen.getByText(/Göndərilməmiş mətniniz/)).toBeInTheDocument();
    await userEvent.click(button);
    expect(worker.postMessage).not.toHaveBeenCalled();

    field.value = "";
    fireEvent.input(field);
    await waitFor(() => expect(button).toBeEnabled());
  });
});

describe("the offline banner", () => {
  it("names the time of the stored data", () => {
    renderWithIntl(
      <OfflineBanner variant="cached" lastUpdated={Date.parse("2026-11-02T07:30:00Z")} />,
    );
    expect(screen.getByText("İnternet bağlantısı yoxdur")).toBeInTheDocument();
    expect(screen.getByText(/Son yenilənmə: .*11:30/)).toBeInTheDocument();
    expect(screen.getByText(/yalnız oxumaq olar/)).toBeInTheDocument();
  });

  it("appears above the app when the connection drops and goes when it returns", async () => {
    renderWithIntl(<PwaNotices />);
    expect(screen.queryByText("İnternet bağlantısı yoxdur")).not.toBeInTheDocument();
    act(() => setOnline(false));
    expect(await screen.findByText("İnternet bağlantısı yoxdur")).toBeInTheDocument();
    expect(
      screen.getByText(/Göndərilməmiş mesajlar bağlantı bərpa olunanda göndəriləcək/),
    ).toBeInTheDocument();
    act(() => setOnline(true));
    await waitFor(() =>
      expect(screen.queryByText("İnternet bağlantısı yoxdur")).not.toBeInTheDocument(),
    );
  });
});

describe("when to offer installing", () => {
  const eligible = { visits: 2, dismissed: false, standalone: false, canPrompt: true, ios: false };

  it("never on the first visit, after dismissal, inside the installed app or without a way to install", () => {
    expect(shouldOffer(eligible)).toBe(true);
    expect(shouldOffer({ ...eligible, visits: 1 })).toBe(false);
    expect(shouldOffer({ ...eligible, dismissed: true })).toBe(false);
    expect(shouldOffer({ ...eligible, standalone: true })).toBe(false);
    expect(shouldOffer({ ...eligible, canPrompt: false })).toBe(false);
    expect(shouldOffer({ ...eligible, canPrompt: false, ios: true })).toBe(true);
  });

  it("counts one visit per browser session", () => {
    expect(recordVisit()).toBe(1);
    expect(recordVisit()).toBe(1);
    sessionStorage.clear();
    expect(recordVisit()).toBe(2);
  });

  it("does not show on the first visit, shows on the second and is remembered once dismissed", async () => {
    const offer = () => {
      const event = new Event("beforeinstallprompt", { cancelable: true });
      Object.assign(event, { prompt: vi.fn(async () => undefined) });
      act(() => void window.dispatchEvent(event));
    };

    const first = renderWithIntl(<InstallPrompt />);
    offer();
    await act(async () => undefined);
    expect(screen.queryByText(/quraşdırın/)).not.toBeInTheDocument();
    first.unmount();

    sessionStorage.clear();
    renderWithIntl(<InstallPrompt />);
    offer();
    expect(await screen.findByText("SmartAzMİU-nu cihazınıza quraşdırın")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Bağlayın" }));
    expect(screen.queryByText("SmartAzMİU-nu cihazınıza quraşdırın")).not.toBeInTheDocument();
    expect(isDismissed()).toBe(true);
  });
});

const week = (start: string): Schedule["days"] =>
  Array.from({ length: 7 }, (_, index) => ({
    date: new Date(Date.parse(`${start}T00:00:00Z`) + index * 86_400_000)
      .toISOString()
      .slice(0, 10),
    parity: "upper" as const,
    classes:
      index === 0
        ? [
            {
              id: "e1",
              date: start,
              starts_at: "08:30",
              ends_at: "09:50",
              subject: { code: "IQT-2101", name: "Mikroiqtisadiyyat" },
              class_type: "lecture" as const,
              room: {
                code: "1-301",
                name: "Mühazirə zalı",
                building: "Tədris korpusu 1",
                floor: "3",
              },
              teachers: ["Şəhla Ağayeva"],
              groups: ["765a2"],
              status: "scheduled" as const,
              original_date: start,
              original_starts_at: "08:30",
              moved_to: null,
              room_changed: false,
              teacher_changed: false,
              note: "",
            },
          ]
        : [],
  }));

async function storeEverything() {
  await claimDevice(USER, SESSION_END);
  await setOfflineEnabled(USER, true, SESSION_END);
  const today = new Date().toISOString().slice(0, 10);
  const monday = new Date(Date.parse(`${today}T00:00:00Z`));
  monday.setUTCDate(monday.getUTCDate() - ((monday.getUTCDay() + 6) % 7));
  const start = monday.toISOString().slice(0, 10);
  const nextStart = new Date(monday.getTime() + 7 * 86_400_000).toISOString().slice(0, 10);
  const schedule: Schedule = {
    start,
    end: new Date(monday.getTime() + 13 * 86_400_000).toISOString().slice(0, 10),
    today,
    days: [...week(start), ...week(nextStart)],
  };
  await putSnapshot(USER, "schedule", "", schedule, Date.parse("2026-11-02T07:30:00Z"));
  const list: ChannelList = {
    channels: [{ id: "c1", name: "İqtisadiyyat — 765a2", context: "Mikroiqtisadiyyat" }],
  };
  await putSnapshot(USER, "channels", "", list);
  const history: ChannelHistory = {
    channel: list.channels[0]!,
    messages: [
      {
        id: "1001",
        authorName: "Ramin Əliyev",
        anonymous: false,
        body: "Mühazirə **1-301**-də olacaq.",
        state: "visible",
        createdAt: "2026-11-02T08:30:00Z",
        edited: false,
        mentions: [],
        attachmentNames: ["cədvəl.pdf"],
      },
      {
        id: "1002",
        authorName: "Aysel Məmmədova",
        anonymous: false,
        body: "",
        state: "blocked",
        createdAt: "2026-11-02T08:31:00Z",
        edited: false,
        mentions: [],
        attachmentNames: [],
      },
    ],
  };
  await putSnapshot(USER, "channel", "c1", history);
}

describe("the offline page", () => {
  it("shows the stored schedule and channel history, read-only, with the time they were stored", async () => {
    await storeEverything();
    setOnline(false);
    renderWithIntl(<OfflineApp />);

    expect(await screen.findByText("Mikroiqtisadiyyat")).toBeInTheDocument();
    expect(screen.getByText(/Son yenilənmə: .*11:30/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bu həftə" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    // The room is text, not a link to the map, which needs the network.
    expect(screen.queryByRole("link", { name: /xəritədə/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Növbəti həftə" }));
    expect(screen.getByRole("button", { name: "Növbəti həftə" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    await userEvent.click(screen.getByRole("tab", { name: "Kanallar" }));
    await userEvent.click(screen.getByRole("button", { name: /İqtisadiyyat — 765a2/ }));
    expect(screen.getByText("1-301")).toBeInTheDocument();
    expect(screen.getByText(/Qoşmalar: cədvəl.pdf/)).toBeInTheDocument();
    expect(screen.getByText("Bloklanmış istifadəçinin mesajı.")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("says nothing is stored on a device that never stored anything", async () => {
    setOnline(false);
    renderWithIntl(<OfflineApp />);
    expect(await screen.findByText(/saxlanmış məlumat yoxdur/)).toBeInTheDocument();
  });

  it("says storing is off when the user never switched it on", async () => {
    await claimDevice(USER, SESSION_END);
    setOnline(false);
    renderWithIntl(<OfflineApp />);
    expect(await screen.findByText(/Oflayn saxlama bu cihazda aktiv deyil/)).toBeInTheDocument();
  });

  it("shows nothing of an ended session and deletes it, though no server can be asked", async () => {
    await storeEverything();
    await claimDevice(USER, Math.floor(Date.now() / 1000) - 5);
    setOnline(false);
    renderWithIntl(<OfflineApp />);
    expect(await screen.findByText(/Sessiyanız bitib/)).toBeInTheDocument();
    expect(screen.queryByText("Mikroiqtisadiyyat")).not.toBeInTheDocument();
    expect(await readDevice()).toBeNull();
  });

  it("wipes on sign-out and remembers the server call until the connection returns", async () => {
    await storeEverything();
    setOnline(false);
    renderWithIntl(<OfflineApp />);
    await screen.findByText("Mikroiqtisadiyyat");

    await userEvent.click(screen.getByRole("button", { name: "Çıxış edin" }));

    expect(await screen.findByText(/Bu cihazdan çıxış etdiniz/)).toBeInTheDocument();
    expect(await readDevice()).toBeNull();
    expect(localStorage.getItem(SIGN_OUT_PENDING_KEY)).not.toBeNull();
    expect(screen.queryByText("Mikroiqtisadiyyat")).not.toBeInTheDocument();
  });

  it("points back to the app when the connection returns", async () => {
    await storeEverything();
    renderWithIntl(<OfflineApp />);
    expect(await screen.findByText("Bağlantı bərpa olundu")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Tətbiqə qayıdın" })).toHaveAttribute("href", "/");
  });
});
