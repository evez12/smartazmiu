import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { ApiProvider } from "@/lib/api/provider";
import { fetchMock, json, serve } from "@/test/api";
import { renderWithIntl } from "@/test/render";

import { ExamsPage } from "./exams-page";
import { countdown, mapLink } from "./model";
import { PapersPage } from "./papers-page";
import { SlotsAdmin } from "./slots-admin";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/exams",
}));

beforeEach(() => vi.stubGlobal("fetch", fetchMock));
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

function wrap(ui: React.ReactNode) {
  return renderWithIntl(
    <ApiProvider csrfToken="csrf-0123">
      <ToastProvider>{ui}</ToastProvider>
    </ApiProvider>,
  );
}

const RETRY_WAIT = { timeout: 4000 };
const OFFERING = {
  id: "o-1",
  subject_name: "Statistika",
  subject_code: "IQT-2102",
  groups: ["765a2"],
  semester: "2026 Payız",
};

describe("countdown", () => {
  const start = "2027-01-14T06:00:00Z";
  const end = "2027-01-14T07:30:00Z";
  const at = (iso: string) => Date.parse(iso);

  it("counts down in the largest unit that fits and stays running until the end", () => {
    expect(countdown(start, end, at("2027-01-10T04:30:00Z"))).toEqual({
      kind: "days",
      days: 4,
      hours: 1,
    });
    expect(countdown(start, end, at("2027-01-14T02:45:00Z"))).toEqual({
      kind: "hours",
      hours: 3,
      minutes: 15,
    });
    expect(countdown(start, end, at("2027-01-14T05:30:30Z"))).toEqual({
      kind: "minutes",
      minutes: 30,
    });
    expect(countdown(start, end, at("2027-01-14T05:59:59Z"))).toEqual({
      kind: "minutes",
      minutes: 1,
    });
    expect(countdown(start, end, at("2027-01-14T06:00:00Z"))).toEqual({ kind: "running" });
    expect(countdown(start, end, at("2027-01-14T07:29:59Z"))).toEqual({ kind: "running" });
  });

  it("links a room to the campus map", () => {
    expect(mapLink("1-301")).toBe("/map?room=1-301");
  });
});

describe("my exams", () => {
  it("lists exams with the room on the map and a calendar file", async () => {
    serve({
      "GET /api/v1/exams/mine": () =>
        json({
          items: [
            {
              id: "e-1",
              offering: OFFERING,
              starts_at: "2099-01-14T06:00:00Z",
              ends_at: "2099-01-14T07:30:00Z",
              room_code: "2-204",
              overlaps: [],
            },
            {
              id: "e-2",
              offering: { ...OFFERING, id: "o-2", subject_name: "Fizika" },
              starts_at: "2099-01-18T06:00:00Z",
              ends_at: "2099-01-18T07:30:00Z",
              room_code: null,
              overlaps: [],
            },
          ],
        }),
    });
    wrap(<ExamsPage />);
    const card = (await screen.findByRole("heading", { name: "Statistika" })).closest("article")!;
    expect(within(card).getByText("Statistika · 765a2 · 2026 Payız")).toBeVisible();
    expect(within(card).getByRole("link", { name: "Otaq 2-204" })).toHaveAttribute(
      "href",
      "/map?room=2-204",
    );
    expect(within(card).getByText(/gün .* saat qalıb/)).toBeVisible();
    expect(screen.getByText("Otaq hələ elan olunmayıb.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Təqvimə əlavə et" })).toHaveAttribute(
      "href",
      "/api/v1/exams/mine.ics",
    );
    expect(screen.getByRole("link", { name: "Keçmiş imtahan kağızları" })).toHaveAttribute(
      "href",
      "/exams/papers",
    );
  });

  it("says so when there are none, and retries after a failure", async () => {
    serve({ "GET /api/v1/exams/mine": () => json({ items: [] }) });
    const { unmount } = wrap(<ExamsPage />);
    expect(await screen.findByText("Yaxın vaxtda imtahanınız yoxdur.")).toBeVisible();
    expect(screen.queryByRole("link", { name: "Təqvimə əlavə et" })).not.toBeInTheDocument();
    unmount();

    serve({ "GET /api/v1/exams/mine": () => json({ error: { code: "x", message: "" } }, 500) });
    wrap(<ExamsPage />);
    expect(
      await screen.findByText(
        "İmtahanlar yüklənmədi. Bir az sonra yenidən cəhd edin.",
        {},
        RETRY_WAIT,
      ),
    ).toBeVisible();
  });
});

describe("the dean's office", () => {
  const slot = {
    id: "e-1",
    offering: OFFERING,
    starts_at: "2027-01-14T06:00:00Z",
    ends_at: "2027-01-14T07:30:00Z",
    room_code: "2-204",
    overlaps: [
      {
        kind: "group",
        slot_id: "e-2",
        offering: { ...OFFERING, id: "o-2", subject_name: "Mikroiqtisadiyyat" },
        starts_at: "2027-01-14T06:30:00Z",
        ends_at: "2027-01-14T08:00:00Z",
      },
    ],
  };

  it("shows collisions in the list and warns after adding an exam that collides", async () => {
    serve({
      "GET /api/v1/exams/slots": () => json({ items: [slot] }),
      "GET /api/v1/coursework/offerings": () => json({ items: [OFFERING] }),
      "POST /api/v1/exams/slots": () => json(slot, 201),
    });
    wrap(<SlotsAdmin />);
    const row = (
      await screen.findByRole("cell", { name: "Statistika · 765a2 · 2026 Payız" })
    ).closest("tr")!;
    expect(within(row).getByText("1 toqquşma")).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: "İmtahanı əlavə et" }));
    expect(screen.getByText("Fənni seçin.")).toBeVisible();
    expect(screen.getByText("Başlama vaxtını yazın.")).toBeVisible();

    await userEvent.selectOptions(screen.getByLabelText(/Fənn və qrup/), "o-1");
    await userEvent.type(screen.getByLabelText(/Başlama vaxtı/), "2027-01-14T10:00");
    await userEvent.type(screen.getByLabelText(/Bitmə vaxtı/), "2027-01-14T09:00");
    await userEvent.click(screen.getByRole("button", { name: "İmtahanı əlavə et" }));
    expect(screen.getByText("Bitmə vaxtı başlama vaxtından sonra olmalıdır.")).toBeVisible();

    await userEvent.clear(screen.getByLabelText(/Bitmə vaxtı/));
    await userEvent.type(screen.getByLabelText(/Bitmə vaxtı/), "2027-01-14T11:30");
    await userEvent.type(screen.getByLabelText("Otaq"), "2-204");
    await userEvent.click(screen.getByRole("button", { name: "İmtahanı əlavə et" }));
    expect(await screen.findByText("Bu imtahan başqa imtahanla üst-üstə düşür")).toBeVisible();
    expect(screen.getByText(/Eyni qrupun imtahanı: Mikroiqtisadiyyat/)).toBeVisible();
    const post = fetchMock.mock.calls.map(([r]) => r).find((r) => r.method === "POST")!;
    expect(await post.clone().json()).toEqual({
      course_offering_id: "o-1",
      starts_at: "2027-01-14T10:00:00+04:00",
      ends_at: "2027-01-14T11:30:00+04:00",
      room_code: "2-204",
    });
  });

  it("confirms before removing an exam", async () => {
    serve({
      "GET /api/v1/exams/slots": () => json({ items: [{ ...slot, overlaps: [] }] }),
      "GET /api/v1/coursework/offerings": () => json({ items: [OFFERING] }),
      "DELETE /api/v1/exams/slots/e-1": () => new Response(null, { status: 204 }),
    });
    wrap(<SlotsAdmin />);
    const row = (
      await screen.findByRole("cell", { name: "Statistika · 765a2 · 2026 Payız" })
    ).closest("tr")!;
    expect(within(row).getByText("Toqquşma yoxdur")).toBeVisible();
    await userEvent.click(within(row).getByRole("button", { name: "Sil" }));
    const dialog = await screen.findByRole("dialog");
    expect(fetchMock.mock.calls.some(([r]) => r.method === "DELETE")).toBe(false);
    await userEvent.click(within(dialog).getByRole("button", { name: "Sil" }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([r]) => r.method === "DELETE")).toBe(true),
    );
  });
});

describe("past papers", () => {
  const paper = {
    id: "p-1",
    subject_id: "s-1",
    semester: "2025 Payız",
    kind: "final",
    title: "Yekun imtahan, 2025 payız",
    filename: "Yekun.pdf",
    size_bytes: 1_048_576,
    status: "pending",
    scan_status: "clean",
    uploaded_by_me: false,
    can_review: true,
    can_download: true,
    review_note: null,
    created_at: "2026-11-01T08:00:00Z",
  };

  function serveSubject(items: unknown[]) {
    serve({
      "GET /api/v1/exams/papers/subjects": () =>
        json({ items: [{ id: "s-1", code: "IQT-2102", name: "Statistika", pending: 1 }] }),
      "GET /api/v1/exams/papers": () =>
        json({ subject_id: "s-1", subject_name: "Statistika", can_upload: true, items }),
      "GET /api/v1/exams/papers/form": () =>
        json({ semesters: [{ id: "sem-1", label: "2025 Payız" }] }),
      "POST /api/v1/exams/papers/p-1/review": () => json({ ...paper, status: "approved" }),
    });
  }

  it("lets a reviewer approve a pending paper, and shows the rule on the upload form", async () => {
    serveSubject([paper]);
    wrap(<PapersPage />);
    const card = (await screen.findByRole("heading", { name: paper.title })).closest("article")!;
    expect(within(card).getByText("Təsdiq gözləyir")).toBeVisible();
    expect(within(card).getByText("2025 Payız · Yekun imtahanı · 1,0 MB")).toBeVisible();
    expect(screen.getByText(/Cari semestrin imtahan sualları paylaşıla bilməz/)).toBeVisible();
    expect(screen.getByRole("option", { name: "2025 Payız" })).toBeInTheDocument();
    expect(screen.getByText(/IQT-2102 · Statistika/)).toHaveTextContent("1 gözləyir");

    await userEvent.click(within(card).getByRole("button", { name: "Qərar ver" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Qeyd"), "Uyğundur");
    await userEvent.click(within(dialog).getByRole("button", { name: "Təsdiq et" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const post = fetchMock.mock.calls.map(([r]) => r).find((r) => r.url.endsWith("/p-1/review"))!;
    expect(await post.clone().json()).toEqual({ approve: true, note: "Uyğundur" });
  });

  it("shows a student only what they may download, and checks the upload form before sending", async () => {
    serveSubject([
      {
        ...paper,
        can_review: false,
        can_download: false,
        scan_status: "pending",
        uploaded_by_me: true,
      },
    ]);
    wrap(<PapersPage />);
    const card = (await screen.findByRole("heading", { name: paper.title })).closest("article")!;
    expect(within(card).getByText("Yoxlanılır")).toBeVisible();
    expect(within(card).queryByRole("button", { name: "Yüklə" })).not.toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: "Qərar ver" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Kağızı göndər" }));
    expect(screen.getByText("Fayl seçin.")).toBeVisible();
    expect(screen.getByText("Semestri seçin.")).toBeVisible();
    expect(screen.getByText("Ad yazın (ən azı 3 simvol).")).toBeVisible();
    expect(screen.getByText("Davam etmək üçün təsdiq qutusunu işarələyin.")).toBeVisible();
    expect(fetchMock.mock.calls.some(([r]) => r.method === "POST")).toBe(false);
  });

  it("explains an empty subject list", async () => {
    serve({ "GET /api/v1/exams/papers/subjects": () => json({ items: [] }) });
    wrap(<PapersPage />);
    expect(await screen.findByText("Hələ fənniniz yoxdur.")).toBeVisible();
  });
});
