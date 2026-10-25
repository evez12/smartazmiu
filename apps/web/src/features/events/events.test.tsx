import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { ApiProvider } from "@/lib/api/provider";
import { formatDateTimeRange } from "@/lib/format";
import { renderWithIntl } from "@/test/render";

import { CheckInDesk } from "./check-in";
import { EventFacts, EventTags } from "./event-facts";
import { EventEditor } from "./event-editor";
import type { EventItem } from "./model";
import { Rsvp } from "./rsvp";
import { TicketQr } from "./ticket-qr";

const push = vi.fn();
const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh }) }));

const fetchMock = vi.fn<(request: Request) => Promise<Response>>();

beforeEach(() => vi.stubGlobal("fetch", fetchMock));
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  push.mockReset();
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

const inOneDay = new Date(Date.now() + 24 * 3600 * 1000).toISOString();
const inOneDayPlusTwo = new Date(Date.now() + 26 * 3600 * 1000).toISOString();

function event(overrides: Partial<EventItem> = {}): EventItem {
  return {
    id: "01a174e0-0000-7000-8000-000000000001",
    title: "Memarlıq sərgisi: tələbə layihələri",
    description: "Birinci kurs tələbələrinin layihələri.",
    starts_at: inOneDay,
    ends_at: inOneDayPlusTwo,
    room: { code: "1-305", name: "Auditoriya" },
    location: "",
    capacity: 30,
    going: 12,
    spots_left: 18,
    audience: {
      type: "faculty",
      target_id: "f",
      label: "Tikinti iqtisadiyyatı fakültəsi",
      detail: "",
    },
    status: "published",
    version: 1,
    my_registration: null,
    ...overrides,
  };
}

describe("event display", () => {
  it("formats a range within one Baku day compactly", () => {
    expect(formatDateTimeRange("2026-12-01T10:00:00Z", "2026-12-01T12:30:00Z")).toBe(
      "1 Dekabr 2026, 14:00–16:30",
    );
    // 19:00–21:00 UTC crosses midnight in Baku.
    expect(formatDateTimeRange("2026-12-01T19:00:00Z", "2026-12-01T21:00:00Z")).toBe(
      "1 Dekabr 2026, 23:00 – 2 Dekabr 2026, 01:00",
    );
  });

  it("shows time with its zone, the room on the map, places and the audience", () => {
    renderWithIntl(<EventFacts event={event()} />);
    expect(screen.getByText("(Bakı vaxtı)")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Otaq 1-305 · Auditoriya, xəritədə göstərin" }),
    ).toHaveAttribute("href", "/map?room=1-305");
    expect(screen.getByText("18 boş yer (12 / 30)")).toBeInTheDocument();
    expect(screen.getByText(/Fakültə · Tikinti iqtisadiyyatı fakültəsi/)).toBeInTheDocument();
  });

  it("labels states with text", () => {
    const { rerender } = renderWithIntl(<EventTags event={event({ status: "cancelled" })} />);
    expect(screen.getByText("Ləğv edilib")).toBeInTheDocument();
    rerender(
      <EventTags
        event={event({
          my_registration: { status: "going", ticket_code: "SA1.x.y", checked_in_at: null },
        })}
      />,
    );
    expect(screen.getByText("Qeydiyyatdan keçmisiniz")).toBeInTheDocument();
    rerender(<EventTags event={event({ spots_left: 0 })} />);
    expect(screen.getByText("Yer yoxdur")).toBeInTheDocument();
  });

  it("draws the ticket as an accessible QR image", () => {
    renderWithIntl(
      <TicketQr code="SA1.0123456789abcdef0123456789abcdef.c2lnbmF0dXJl" label="Bilet" />,
    );
    const image = screen.getByRole("img", { name: "Bilet" });
    expect(image.querySelector("path")!.getAttribute("d")).toMatch(/^M\d+ \d+h1v1h-1z/);
    expect(image.querySelector("rect")).toHaveAttribute("fill", "var(--qr-light)");
  });
});

describe("Rsvp", () => {
  it("registers and refreshes the page to show the ticket", async () => {
    fetchMock.mockResolvedValue(json(event()));
    renderInApp(<Rsvp event={event()} />);
    await userEvent.click(screen.getByRole("button", { name: "Qeydiyyatdan keçin" }));
    await waitFor(() => expect(refresh).toHaveBeenCalled());
    expect(fetchMock.mock.calls[0]![0].method).toBe("PUT");
  });

  it("asks before withdrawing, because the ticket stops working", async () => {
    fetchMock.mockResolvedValue(json(event()));
    const going = event({
      my_registration: { status: "going", ticket_code: "SA1.x.y", checked_in_at: null },
    });
    renderInApp(<Rsvp event={going} />);
    await userEvent.click(screen.getByRole("button", { name: "Qeydiyyatı ləğv edin" }));
    const dialog = screen.getByRole("alertdialog", { name: "Qeydiyyat ləğv edilsin?" });
    expect(dialog).toHaveTextContent("Biletiniz etibarsız olacaq.");
    await userEvent.click(within(dialog).getByRole("button", { name: "Qeydiyyatı ləğv edin" }));
    await waitFor(() => expect(fetchMock.mock.calls[0]![0].method).toBe("DELETE"));
  });

  it("explains a full event and a started one", () => {
    const { rerender } = renderInApp(<Rsvp event={event({ spots_left: 0 })} />);
    expect(screen.getByRole("button", { name: "Qeydiyyatdan keçin" })).toBeDisabled();
    rerender(
      <ApiProvider csrfToken="csrf-0123">
        <ToastProvider>
          <Rsvp event={event({ starts_at: new Date(Date.now() - 60_000).toISOString() })} />
        </ToastProvider>
      </ApiProvider>,
    );
    expect(screen.getByText("Tədbir başlayıb; qeydiyyat bağlıdır.")).toBeInTheDocument();
  });
});

describe("EventEditor", () => {
  it("explains what is missing", async () => {
    renderInApp(<EventEditor />);
    await userEvent.type(screen.getByRole("spinbutton", { name: /Yer sayı/ }), "0");
    await userEvent.click(screen.getByRole("button", { name: "Dərc edin" }));
    expect(screen.getByText("Tədbirin adını yazın.")).toBeInTheDocument();
    expect(screen.getByText("Başlama və bitmə vaxtını seçin.")).toBeInTheDocument();
    expect(screen.getByText("Otaq kodunu və ya yeri göstərin.")).toBeInTheDocument();
    expect(screen.getByText("Müsbət tam ədəd yazın.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("publishes with Baku times, the room and an idempotency key", async () => {
    fetchMock.mockResolvedValue(json(event(), 201));
    renderInApp(<EventEditor />);
    await userEvent.type(screen.getByRole("textbox", { name: /^Ad/ }), "Karyera günü");
    await userEvent.type(screen.getByRole("textbox", { name: /Təsvir/ }), "Şirkətlərlə görüş.");
    await userEvent.type(screen.getByLabelText(/Başlama vaxtı/), "2026-12-05T11:00");
    await userEvent.type(screen.getByLabelText(/Bitmə vaxtı/), "2026-12-05T15:00");
    await userEvent.type(screen.getByRole("textbox", { name: /Otaq kodu/ }), "1-305");
    await userEvent.click(screen.getByRole("button", { name: "Dərc edin" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith(`/events/${event().id}`));
    const request = fetchMock.mock.calls[0]![0];
    expect(request.headers.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
    expect(await request.json()).toEqual({
      title: "Karyera günü",
      description: "Şirkətlərlə görüş.",
      starts_at: "2026-12-05T11:00:00+04:00",
      ends_at: "2026-12-05T15:00:00+04:00",
      room_code: "1-305",
      location: "",
      capacity: null,
      audience: { type: "university", target_id: null },
    });
  });
});

describe("CheckInDesk", () => {
  const attendees = {
    going: 2,
    checked_in: 1,
    items: [
      {
        registration_id: "r-aysel",
        name: "Aysel Məmmədova",
        group: "765a2",
        checked_in_at: "2026-12-05T07:05:00Z",
        check_in_method: "scan",
      },
      {
        registration_id: "r-ramin",
        name: "Ramin Əliyev",
        group: "765a2",
        checked_in_at: null,
        check_in_method: null,
      },
    ],
  };

  it("admits by code, explains a repeated ticket and checks people in from the list", async () => {
    const answers = [
      json({
        name: "Ramin Əliyev",
        group: "765a2",
        checked_in_at: "2026-12-05T07:06:00Z",
        check_in_method: "scan",
      }),
      json(
        {
          error: {
            code: "events.already_checked_in",
            message: "Bu iştirakçı artıq qeydiyyatdan keçib.",
            details: { name: "Aysel Məmmədova", checked_in_at: "2026-12-05T07:05:00Z" },
          },
        },
        409,
      ),
      json({
        name: "Ramin Əliyev",
        group: "765a2",
        checked_in_at: "2026-12-05T07:07:00Z",
        check_in_method: "manual",
      }),
    ];
    fetchMock.mockImplementation(async (request) =>
      request.method === "GET" ? json(attendees) : answers.shift()!,
    );
    renderInApp(<CheckInDesk eventId="e-1" />);
    expect(await screen.findByText("1 / 2 nəfər girişdə qeyd olunub")).toBeInTheDocument();

    const field = screen.getByRole("textbox", { name: /Bilet kodu/ });
    expect(field).toHaveFocus();
    await userEvent.type(field, "SA1.abc.def{Enter}");
    expect(await screen.findByText("Ramin Əliyev (765a2) qeydiyyata alındı")).toBeInTheDocument();
    expect(field).toHaveValue("");

    await userEvent.type(field, "SA1.abc.def{Enter}");
    expect(
      await screen.findByText("Aysel Məmmədova artıq 11:05 qeydiyyatdan keçib."),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Qeydə alın" }));
    await waitFor(() => {
      const posts = fetchMock.mock.calls.filter(([request]) => request.method === "POST");
      expect(posts).toHaveLength(3);
    });
    const manual = fetchMock.mock.calls.filter(([request]) => request.method === "POST")[2]![0];
    expect(await manual.json()).toEqual({ registration_id: "r-ramin" });
  });

  it("offers the camera only where the browser can read QR codes", async () => {
    fetchMock.mockResolvedValue(json({ going: 0, checked_in: 0, items: [] }));
    renderInApp(<CheckInDesk eventId="e-1" />);
    expect(await screen.findByText("Bu tədbirə hələ qeydiyyat yoxdur.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Kamera ilə oxudun" })).not.toBeInTheDocument();
  });
});
