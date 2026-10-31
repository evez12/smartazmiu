import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiProvider } from "@/lib/api/provider";
import { fetchMock, json, serve } from "@/test/api";
import { renderWithIntl } from "@/test/render";

import { AttendancePage } from "./attendance-page";
import { MyCoursePage, ReportPage } from "./report-pages";
import { ScanPage } from "./scan-page";
import { SessionScreen } from "./session-screen";

const router = { refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => "/attendance" }));

beforeEach(() => vi.stubGlobal("fetch", fetchMock));
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  router.push.mockReset();
});

function wrap(ui: React.ReactNode) {
  return renderWithIntl(<ApiProvider csrfToken="csrf-0123">{ui}</ApiProvider>);
}

const RETRY_WAIT = { timeout: 4000 };
const OFFERING = {
  id: "o-1",
  subject_name: "Statistika",
  subject_code: "IQT-2102",
  groups: ["765a2"],
  semester: "2026 Payız",
};
const MEETING = {
  id: "s-1",
  offering: OFFERING,
  title: "Mühazirə 5",
  opened_at: "2026-11-02T06:00:00Z",
  expires_at: "2026-11-02T07:30:00Z",
  closed_at: null,
  is_open: true,
  present: 1,
  enrolled: 3,
};
const ROSTER = [
  {
    student_id: "u-1",
    display_name: "Aysel Məmmədova",
    university_id: "25765201",
    group: "765a2",
    present: true,
    method: "qr",
    checked_in_at: "2026-11-02T06:03:00Z",
    reason: null,
  },
  {
    student_id: "u-2",
    display_name: "Nihad Vəliyev",
    university_id: "25765215",
    group: "765a2",
    present: false,
    method: null,
    checked_in_at: null,
    reason: null,
  },
];

describe("the attendance page", () => {
  it("shows a student their rate per course and a scan action", async () => {
    serve({
      "GET /api/v1/attendance/my": () =>
        json({
          items: [
            { offering: OFFERING, attended: 7, total: 8, rate: 0.875, sessions: [] },
            {
              offering: { ...OFFERING, id: "o-2", subject_name: "Fizika" },
              attended: 3,
              total: 8,
              rate: 0.375,
              sessions: [],
            },
          ],
        }),
      "GET /api/v1/attendance/offerings": () => json({ items: [] }),
    });
    wrap(<AttendancePage />);
    const statistika = (
      await screen.findByRole("link", { name: "Statistika · 765a2 · 2026 Payız" })
    ).closest("li")!;
    expect(within(statistika).getByText("7 / 8 dərs")).toBeVisible();
    expect(within(statistika).getByText("88 %")).toBeVisible();
    expect(screen.getByText("38 %")).toBeVisible();
    expect(screen.getByRole("link", { name: "İştirakı qeyd et" })).toHaveAttribute(
      "href",
      "/attendance/scan",
    );
    expect(screen.queryByRole("button", { name: "Dərsi aç" })).not.toBeInTheDocument();
  });

  it("lets a teacher open a meeting and goes to its screen", async () => {
    serve({
      "GET /api/v1/attendance/my": () => json({ items: [] }),
      "GET /api/v1/attendance/offerings": () => json({ items: [{ ...OFFERING, role: "manager" }] }),
      "GET /api/v1/attendance/sessions": () => json({ items: [] }),
      "POST /api/v1/attendance/sessions": () => json(MEETING, 201),
    });
    wrap(<AttendancePage />);
    await userEvent.type(await screen.findByLabelText("Dərsin adı"), "Mühazirə 5");
    await userEvent.click(screen.getByRole("button", { name: "Dərsi aç" }));
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/attendance/sessions/s-1"));
    const post = fetchMock.mock.calls.map(([r]) => r).find((r) => r.method === "POST")!;
    expect(await post.clone().json()).toEqual({
      course_offering_id: "o-1",
      title: "Mühazirə 5",
      duration_minutes: 90,
    });
    expect(screen.getByRole("link", { name: "Hesabat" })).toHaveAttribute(
      "href",
      "/attendance/reports/o-1",
    );
    expect(screen.getByRole("link", { name: "CSV yüklə" })).toHaveAttribute(
      "href",
      "/api/v1/attendance/offerings/o-1/report.csv",
    );
  });

  it("points to the open meeting instead of the form, and tells a curator they only read", async () => {
    serve({
      "GET /api/v1/attendance/my": () => json({ items: [] }),
      "GET /api/v1/attendance/offerings": () => json({ items: [{ ...OFFERING, role: "manager" }] }),
      "GET /api/v1/attendance/sessions": () => json({ items: [MEETING] }),
    });
    const { unmount } = wrap(<AttendancePage />);
    expect(await screen.findByText("Bu fənn üçün açıq dərs var.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Davam et" })).toHaveAttribute(
      "href",
      "/attendance/sessions/s-1",
    );
    expect(screen.queryByLabelText("Dərsin adı")).not.toBeInTheDocument();
    unmount();

    serve({
      "GET /api/v1/attendance/my": () => json({ items: [] }),
      "GET /api/v1/attendance/offerings": () => json({ items: [{ ...OFFERING, role: "curator" }] }),
    });
    wrap(<AttendancePage />);
    expect(
      await screen.findByText("Kurator kimi yalnız qruplarınızın hesabatını görürsünüz."),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "Dərsi aç" })).not.toBeInTheDocument();
  });

  it("says so when there is nothing, and offers a retry when loading fails", async () => {
    serve({
      "GET /api/v1/attendance/my": () => json({ items: [] }),
      "GET /api/v1/attendance/offerings": () => json({ items: [] }),
    });
    const { unmount } = wrap(<AttendancePage />);
    expect(await screen.findByText("Davamiyyət üçün fənniniz yoxdur.")).toBeVisible();
    unmount();

    serve({
      "GET /api/v1/attendance/my": () => json({ error: { code: "x", message: "" } }, 500),
      "GET /api/v1/attendance/offerings": () => json({ items: [] }),
    });
    wrap(<AttendancePage />);
    expect(
      await screen.findByText(
        "Davamiyyət yüklənmədi. Bir az sonra yenidən cəhd edin.",
        {},
        RETRY_WAIT,
      ),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Yenidən cəhd et" })).toBeVisible();
  });
});

describe("the teacher screen", () => {
  const code = {
    qr: "SAT1.0001.5.abc",
    digits: "042917",
    valid_until: "2026-11-02T06:10:30Z",
    server_time: "2026-11-02T06:10:12Z",
    present: 2,
    enrolled: 3,
    is_open: true,
  };

  it("shows the code, the live count and the roster, and a manual mark needs a reason", async () => {
    serve({
      "GET /api/v1/attendance/sessions/s-1": () => json({ ...MEETING, roster: ROSTER }),
      "GET /api/v1/attendance/sessions/s-1/code": () => json(code),
      "PUT /api/v1/attendance/sessions/s-1/students/u-2": () =>
        json({ ...ROSTER[1], present: true, method: "manual", reason: "Telefonu yox idi" }),
    });
    wrap(<SessionScreen sessionId="s-1" />);
    expect(await screen.findByLabelText("Altı rəqəmli kod")).toHaveTextContent("042 917");
    expect(screen.getByRole("img", { name: "İştirakı qeyd etmək üçün QR kod" })).toBeVisible();
    expect(await screen.findByText("2 / 3 tələbə")).toBeVisible();
    expect(screen.getByText(/Yeni kod \d+ saniyə sonra/)).toBeVisible();
    const row = screen.getByRole("cell", { name: "Nihad Vəliyev" }).closest("tr")!;
    expect(within(row).getByText("Yoxdur")).toBeVisible();

    await userEvent.click(within(row).getByRole("button", { name: "İştirak qeyd et" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "İştirak qeyd et" }));
    expect(within(dialog).getByText("Səbəbi yazın (ən azı 3 simvol).")).toBeVisible();
    expect(fetchMock.mock.calls.some(([r]) => r.method === "PUT")).toBe(false);

    await userEvent.type(within(dialog).getByLabelText(/Səbəb/), "Telefonu yox idi");
    await userEvent.click(within(dialog).getByRole("button", { name: "İştirak qeyd et" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const put = fetchMock.mock.calls.map(([r]) => r).find((r) => r.method === "PUT")!;
    expect(await put.clone().json()).toEqual({ present: true, reason: "Telefonu yox idi" });
  });

  it("shows a closed meeting without a code", async () => {
    serve({
      "GET /api/v1/attendance/sessions/s-1": () =>
        json({ ...MEETING, is_open: false, closed_at: "2026-11-02T07:00:00Z", roster: ROSTER }),
    });
    wrap(<SessionScreen sessionId="s-1" />);
    expect(await screen.findByText("Bu dərsin iştirak qeydi bağlanıb.")).toBeVisible();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Qeydi bağla" })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([r]) => r.url.endsWith("/code"))).toBe(false);
  });

  it("tells an outsider the meeting is not there", async () => {
    serve({
      "GET /api/v1/attendance/sessions/s-1": () =>
        json({ error: { code: "attendance.not_found", message: "Dərs tapılmadı." } }, 404),
    });
    wrap(<SessionScreen sessionId="s-1" />);
    expect(
      await screen.findByText("Dərs yüklənmədi. Bir az sonra yenidən cəhd edin.", {}, RETRY_WAIT),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "Qeydi bağla" })).not.toBeInTheDocument();
  });
});

describe("the student scanner", () => {
  it("accepts the six digits, with or without a space, and confirms", async () => {
    serve({
      "POST /api/v1/attendance/check-in": () =>
        json({
          session_id: "s-1",
          offering: OFFERING,
          checked_in_at: "2026-11-02T06:03:00Z",
          already_present: false,
        }),
    });
    wrap(<ScanPage />);
    await userEvent.type(screen.getByLabelText("Altı rəqəmli kod"), "042 917");
    await userEvent.click(screen.getByRole("button", { name: "Kodu göndər" }));
    expect(await screen.findByText("İştirakınız qeyd olundu")).toBeVisible();
    expect(screen.getByText(/Statistika · 765a2 · 2026 Payız, saat 10:03/)).toBeVisible();
    const post = fetchMock.mock.calls.map(([r]) => r).find((r) => r.method === "POST")!;
    expect(await post.clone().json()).toEqual({ digits: "042917" });
  });

  it("rejects an incomplete code before sending, and shows the server's reason for a wrong one", async () => {
    serve({
      "POST /api/v1/attendance/check-in": () =>
        json(
          {
            error: {
              code: "attendance.code_invalid",
              message: "Kod düzgün deyil. Müəllimin ekranındakı koda baxıb yenidən cəhd edin.",
            },
          },
          400,
        ),
    });
    wrap(<ScanPage />);
    const input = screen.getByLabelText("Altı rəqəmli kod");
    await userEvent.type(input, "1234");
    await userEvent.click(screen.getByRole("button", { name: "Kodu göndər" }));
    expect(screen.getByText("Altı rəqəm yazın.")).toBeVisible();
    expect(fetchMock).not.toHaveBeenCalled();

    await userEvent.type(input, "56");
    await userEvent.click(screen.getByRole("button", { name: "Kodu göndər" }));
    expect(await screen.findByText("İştirak qeyd olunmadı")).toBeVisible();
    expect(screen.getByText(/Kod düzgün deyil/)).toBeVisible();
  });

  it("reports a repeated check-in as already done", async () => {
    serve({
      "POST /api/v1/attendance/check-in": () =>
        json({
          session_id: "s-1",
          offering: OFFERING,
          checked_in_at: "2026-11-02T06:03:00Z",
          already_present: true,
        }),
    });
    wrap(<ScanPage />);
    await userEvent.type(screen.getByLabelText("Altı rəqəmli kod"), "042917");
    await userEvent.click(screen.getByRole("button", { name: "Kodu göndər" }));
    expect(await screen.findByText("İştirakınız artıq qeyd olunub")).toBeVisible();
  });

  it("falls back to typing when the camera is missing", async () => {
    vi.stubGlobal("navigator", { ...navigator, mediaDevices: undefined });
    wrap(<ScanPage />);
    await userEvent.click(screen.getByRole("button", { name: "Kameranı aç" }));
    expect(
      await screen.findByText(
        "Kameradan istifadə etmək mümkün olmadı. Aşağıda rəqəmli kodu yaza bilərsiniz.",
      ),
    ).toBeVisible();
    expect(screen.getByLabelText("Altı rəqəmli kod")).toBeEnabled();
  });
});

describe("reports", () => {
  it("lists every student with the rate and offers both exports", async () => {
    serve({
      "GET /api/v1/attendance/offerings/o-1/report": () =>
        json({
          offering: OFFERING,
          sessions: [{ id: "s-1", title: "Mühazirə 5", opened_at: "2026-11-02T06:00:00Z" }],
          rows: [
            {
              student_id: "u-1",
              display_name: "Aysel Məmmədova",
              university_id: "25765201",
              group: "765a2",
              attended: 1,
              total: 1,
              rate: 1,
              marks: [true],
            },
            {
              student_id: "u-2",
              display_name: "Nihad Vəliyev",
              university_id: "25765215",
              group: "765a2",
              attended: 0,
              total: 1,
              rate: 0,
              marks: [false],
            },
          ],
        }),
    });
    wrap(<ReportPage offeringId="o-1" />);
    const aysel = (await screen.findByRole("cell", { name: "Aysel Məmmədova" })).closest("tr")!;
    expect(within(aysel).getByText("100 %")).toBeVisible();
    const nihad = screen.getByRole("cell", { name: "Nihad Vəliyev" }).closest("tr")!;
    expect(within(nihad).getByText("0 %")).toBeVisible();
    expect(screen.getByRole("link", { name: "Excel yüklə" })).toHaveAttribute(
      "href",
      "/api/v1/attendance/offerings/o-1/report.xlsx",
    );
  });

  it("shows a student their own meetings, present and absent", async () => {
    serve({
      "GET /api/v1/attendance/my/o-1": () =>
        json({
          offering: OFFERING,
          attended: 1,
          total: 2,
          rate: 0.5,
          sessions: [
            { id: "s-2", title: "Mühazirə 6", opened_at: "2026-11-09T06:00:00Z", present: false },
            { id: "s-1", title: "Mühazirə 5", opened_at: "2026-11-02T06:00:00Z", present: true },
          ],
        }),
    });
    wrap(<MyCoursePage offeringId="o-1" />);
    expect(await screen.findByText("50 %")).toBeVisible();
    const items = within(screen.getByRole("list", { name: "Dərslər" })).getAllByRole("listitem");
    expect(within(items[0]!).getByText("İştirak etməmisiniz")).toBeVisible();
    expect(within(items[1]!).getByText("İştirak etdiniz")).toBeVisible();
  });
});
