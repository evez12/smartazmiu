import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { ApiProvider } from "@/lib/api/provider";
import { fetchMock, json, serve } from "@/test/api";
import { renderWithIntl } from "@/test/render";

import { AssignmentBuilder } from "./assignment-builder";
import { AssignmentPage } from "./assignment-detail";
import { AssignmentsPage } from "./assignments-list";
import { GradeSubmission } from "./grade-submission";

const router = { refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => "/assignments" }));

beforeEach(() => vi.stubGlobal("fetch", fetchMock));
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  router.push.mockReset();
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
const SUMMARY = {
  id: "a-1",
  offering: OFFERING,
  title: "Təsviri statistika",
  available_from: null,
  deadline: "2026-11-20T08:00:00Z",
  max_points: "50.00",
  late_policy: "penalize",
  late_penalty_percent: "25.00",
  can_manage: false,
  my_status: "not_submitted",
  enrolled_count: null,
  submitted_count: null,
  graded_count: null,
};
const DETAIL = {
  ...SUMMARY,
  instructions: "Verilənləri təhlil edib hesabat yazın.",
  can_submit: true,
  submit_blocked: null,
  my_submission: null,
};

describe("the list", () => {
  it("shows a student their status and a teacher the progress of the class and a create button", async () => {
    serve({
      "GET /api/v1/assignments": () =>
        json({
          items: [
            SUMMARY,
            {
              ...SUMMARY,
              id: "a-2",
              title: "Laboratoriya 2",
              can_manage: true,
              my_status: null,
              enrolled_count: 25,
              submitted_count: 18,
              graded_count: 10,
            },
          ],
        }),
      "GET /api/v1/coursework/offerings": () => json({ items: [OFFERING] }),
    });
    wrap(<AssignmentsPage />);
    const mine = (await screen.findByRole("link", { name: "Təsviri statistika" })).closest(
      "article",
    )!;
    expect(within(mine).getByText("Göndərilməyib")).toBeVisible();
    expect(within(mine).getByText("Statistika · 765a2 · 2026 Payız")).toBeVisible();
    const theirs = screen.getByRole("link", { name: "Laboratoriya 2" }).closest("article")!;
    expect(within(theirs).getByText("18 / 25 tələbə göndərib, 10 qiymətləndirilib")).toBeVisible();
    expect(await screen.findByRole("link", { name: "Tapşırıq yaradın" })).toHaveAttribute(
      "href",
      "/assignments/new",
    );
  });

  it("explains the empty state differently for people who cannot create, and offers a retry on failure", async () => {
    serve({
      "GET /api/v1/assignments": () => json({ items: [] }),
      "GET /api/v1/coursework/offerings": () => json({ items: [] }),
    });
    const { unmount } = wrap(<AssignmentsPage />);
    expect(await screen.findByText("Hələ sizin üçün tapşırıq yoxdur.")).toBeVisible();
    expect(screen.queryByRole("link", { name: "Tapşırıq yaradın" })).toBeNull();
    unmount();

    serve({
      "GET /api/v1/assignments": () => json({ error: { code: "x", message: "x" } }, 500),
      "GET /api/v1/coursework/offerings": () => json({ items: [] }),
    });
    wrap(<AssignmentsPage />);
    expect(
      await screen.findByRole("button", { name: "Yenidən cəhd edin" }, RETRY_WAIT),
    ).toBeVisible();
  });
});

describe("the builder", () => {
  it("asks for the course and a title, then sends Baku-time dates and the late policy", async () => {
    let created: Request | null = null;
    serve({
      "GET /api/v1/coursework/offerings": () => json({ items: [OFFERING] }),
      "POST /api/v1/assignments": (request) => {
        created = request.clone();
        return json({ ...DETAIL, can_manage: true }, 201);
      },
    });
    wrap(<AssignmentBuilder />);
    await screen.findByRole("option", { name: "Statistika · 765a2 · 2026 Payız" });
    await userEvent.click(screen.getByRole("button", { name: "Tapşırığı yaradın" }));
    expect(screen.getByText("Fənni seçin.")).toBeVisible();
    expect(screen.getByText("Başlığı yazın.")).toBeVisible();
    expect(created).toBeNull();

    await userEvent.selectOptions(screen.getByLabelText(/Fənn və qrup/), "o-1");
    await userEvent.type(screen.getByLabelText(/^Başlıq/), "Təsviri statistika");
    await userEvent.type(screen.getByLabelText(/^Son tarix/), "2026-11-20T12:00");
    await userEvent.click(screen.getByRole("radio", { name: /Bal azaldılsın/ }));
    await userEvent.clear(screen.getByLabelText(/Azaltma faizi/));
    await userEvent.type(screen.getByLabelText(/Azaltma faizi/), "25");
    await userEvent.click(screen.getByRole("button", { name: "Tapşırığı yaradın" }));
    await waitFor(() => expect(created).not.toBeNull());
    const body = await (created as unknown as Request).json();
    expect(body).toMatchObject({
      course_offering_id: "o-1",
      title: "Təsviri statistika",
      deadline: "2026-11-20T12:00:00+04:00",
      late_policy: "penalize",
      late_penalty_percent: "25",
    });
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/assignments/a-1"));
  });

  it("says so when the user has nothing to add work to", async () => {
    serve({ "GET /api/v1/coursework/offerings": () => json({ items: [] }) });
    wrap(<AssignmentBuilder />);
    expect(
      await screen.findByText("Sizin tapşırıq əlavə edə biləcəyiniz fənn yoxdur."),
    ).toBeVisible();
  });
});

describe("a student's page", () => {
  it("shows the file checks, the grade with the late penalty and no upload once graded", async () => {
    serve({
      "GET /api/v1/assignments/a-1": () =>
        json({
          ...DETAIL,
          my_status: "graded",
          can_submit: false,
          submit_blocked: "graded",
          my_submission: {
            id: "s-1",
            submitted_at: "2026-11-21T08:00:00Z",
            is_late: true,
            files: [
              {
                id: "f-1",
                version: 1,
                filename: "Hesabat.pdf",
                mime: "application/pdf",
                size_bytes: 120000,
                status: "clean",
                previewable: true,
                created_at: "2026-11-21T08:00:00Z",
              },
            ],
            grade: {
              points: "30.00",
              raw_points: "40.00",
              feedback: "Nəticələri daha dəqiq şərh edin.",
              graded_at: "2026-11-22T08:00:00Z",
            },
          },
        }),
    });
    wrap(<AssignmentPage id="a-1" />);
    expect(await screen.findByText("Hesabat.pdf")).toBeVisible();
    expect(screen.getByText("Yoxlanılıb")).toBeVisible();
    expect(screen.getByText("Gecikib")).toBeVisible();
    expect(screen.getByText("30 / 50 bal")).toBeVisible();
    expect(
      screen.getByText("Müəllimin verdiyi bal 40 idi; gecikmə səbəbilə azaldılıb."),
    ).toBeVisible();
    expect(screen.getByText("Nəticələri daha dəqiq şərh edin.")).toBeVisible();
    expect(
      screen.getByText("İşiniz qiymətləndirilib, dəyişiklik etmək mümkün deyil."),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: /Göndərin/ })).toBeNull();
  });

  it("refuses a file type before anything is sent, and tells why a closed assignment takes none", async () => {
    serve({ "GET /api/v1/assignments/a-1": () => json(DETAIL) });
    const { unmount } = wrap(<AssignmentPage id="a-1" />);
    await screen.findByText("Verilənləri təhlil edib hesabat yazın.");
    await userEvent.click(screen.getByRole("button", { name: "Göndərin" }));
    expect(screen.getByText("Fayl seçin.")).toBeVisible();
    await userEvent.upload(
      document.querySelector('input[type="file"]')!,
      new File(["x"], "virus.exe", { type: "application/octet-stream" }),
      { applyAccept: false },
    );
    await userEvent.click(screen.getByRole("button", { name: "Göndərin" }));
    expect(screen.getByText("Bu fayl növü qəbul olunmur.")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    unmount();

    serve({
      "GET /api/v1/assignments/a-1": () =>
        json({ ...DETAIL, can_submit: false, submit_blocked: "closed" }),
    });
    wrap(<AssignmentPage id="a-1" />);
    expect(await screen.findByText("Son tarix keçib, yeni iş qəbul olunmur.")).toBeVisible();
  });
});

describe("a teacher's pages", () => {
  const manager = {
    ...DETAIL,
    can_manage: true,
    my_status: null,
    enrolled_count: 2,
    submitted_count: 1,
    graded_count: 0,
    can_submit: false,
  };

  it("lists every student with their work and links to the one to grade", async () => {
    serve({
      "GET /api/v1/assignments/a-1": () => json(manager),
      "GET /api/v1/assignments/a-1/submissions": () =>
        json({
          items: [
            {
              student: { id: "u-1", display_name: "Aysel Məmmədova", group_code: "765a2" },
              submission_id: "s-1",
              submitted_at: "2026-11-19T08:00:00Z",
              is_late: false,
              file_status: "pending",
              points: null,
              graded: false,
            },
            {
              student: { id: "u-2", display_name: "Ramin Əliyev", group_code: "765a2" },
              submission_id: null,
              submitted_at: null,
              is_late: false,
              file_status: null,
              points: null,
              graded: false,
            },
          ],
        }),
    });
    wrap(<AssignmentPage id="a-1" />);
    const row = (await screen.findByText("Aysel Məmmədova")).closest("tr")!;
    expect(within(row).getByText("Göndərilib")).toBeVisible();
    expect(within(row).getByText("Yoxlanılır")).toBeVisible();
    expect(within(row).getByRole("link", { name: "Qiymətləndirin" })).toHaveAttribute(
      "href",
      "/assignments/a-1/submissions/s-1",
    );
    const other = screen.getByText("Ramin Əliyev").closest("tr")!;
    expect(within(other).getByText("İş göndərilməyib")).toBeVisible();
    expect(within(other).queryByRole("link")).toBeNull();
    expect(screen.queryByRole("button", { name: "Göndərin" })).toBeNull();
  });

  it("checks the points against the maximum before sending and sends what the teacher typed", async () => {
    let graded: Request | null = null;
    const submission = {
      id: "s-1",
      assignment_id: "a-1",
      assignment_title: "Təsviri statistika",
      max_points: "50.00",
      late_policy: "penalize",
      late_penalty_percent: "25.00",
      student: { id: "u-1", display_name: "Aysel Məmmədova", group_code: "765a2" },
      submitted_at: "2026-11-21T08:00:00Z",
      is_late: true,
      files: [],
      grade: null,
    };
    serve({
      "GET /api/v1/assignment-submissions/s-1": () => json(submission),
      "POST /api/v1/assignment-submissions/s-1/grade": (request) => {
        graded = request.clone();
        return json(submission);
      },
    });
    wrap(<GradeSubmission assignmentId="a-1" submissionId="s-1" />);
    expect(
      await screen.findByText("Bu iş gecikib. Yazdığınız baldan 25% çıxılacaq."),
    ).toBeVisible();
    const points = screen.getByLabelText(/Bal \(ən çox 50\)/);
    await userEvent.type(points, "60");
    await userEvent.click(screen.getByRole("button", { name: "Qiyməti yadda saxlayın" }));
    expect(screen.getByText("0 ilə 50 arasında bal yazın.")).toBeVisible();
    expect(graded).toBeNull();
    await userEvent.clear(points);
    await userEvent.type(points, "40,5");
    await userEvent.type(screen.getByLabelText("Rəy"), "Yaxşı iş.");
    await userEvent.click(screen.getByRole("button", { name: "Qiyməti yadda saxlayın" }));
    await waitFor(() => expect(graded).not.toBeNull());
    expect(await (graded as unknown as Request).json()).toEqual({
      points: "40.5",
      feedback: "Yaxşı iş.",
    });
  });
});
