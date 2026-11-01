import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { ApiProvider } from "@/lib/api/provider";
import { fetchMock, json, serve } from "@/test/api";
import { renderWithIntl } from "@/test/render";

import { GpaPage } from "./gpa-page";
import { parseRules } from "./rules-storage";
import { GPA_DEFAULTS } from "./uomg";

beforeEach(() => vi.stubGlobal("fetch", fetchMock));
afterEach(() => {
  window.localStorage.clear();
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

function course(
  id: string,
  subject: string,
  credits: number,
  score: number,
  year: number,
  term: "fall" | "spring",
) {
  return {
    enrollment_id: id,
    subject_id: subject,
    subject_code: subject.toUpperCase(),
    subject_name: `Fənn ${subject}`,
    credits,
    semester_year: year,
    semester_term: term,
    score,
    passed: score >= 51,
  };
}

/** The transcript case of the spec: 30 credits, 2343 points. */
const TRANSCRIPT = [
  course("e1", "a", 5, 81, 2025, "fall"),
  course("e2", "b", 8, 74, 2025, "fall"),
  course("e3", "c", 5, 78, 2025, "fall"),
  course("e4", "d", 8, 75, 2025, "fall"),
  course("e5", "e", 4, 89, 2025, "fall"),
];

describe("GPA calculator", () => {
  it("shows the cumulative and per-semester ÜOMG with the loan highlights", async () => {
    serve({ "GET /api/v1/me/grades": () => json({ items: TRANSCRIPT }) });
    wrap(<GpaPage />);

    expect(await screen.findByTestId("gpa-total")).toHaveTextContent("78.10");
    expect(screen.getByText("Qiymət: C")).toBeVisible();
    const semesters = screen.getByRole("table", { name: "Semestrlər üzrə ÜOMG" });
    expect(within(semesters).getByText("2025 Payız")).toBeVisible();
    expect(
      within(semesters).getByText("71 və yuxarı: tələbə kreditində faiz tətbiq olunmur"),
    ).toBeVisible();
    expect(screen.queryByText(/ən yüksək göstərici/)).toBeNull();
  });

  it("lets the latest attempt replace the old score and shows it in the table", async () => {
    serve({
      "GET /api/v1/me/grades": () =>
        json({
          items: [
            course("e1", "math", 6, 40, 2024, "fall"),
            course("e2", "math", 6, 80, 2025, "spring"),
          ],
        }),
    });
    wrap(<GpaPage />);

    expect(await screen.findByTestId("gpa-total")).toHaveTextContent("80.00");
    expect(screen.getByText("Təkrarla əvəz olunub")).toBeVisible();

    await userEvent.click(screen.getByRole("radio", { name: /Bütün cəhdlər sayılır/ }));
    expect(screen.getByTestId("gpa-total")).toHaveTextContent("60.00");
    expect(screen.queryByText("Təkrarla əvəz olunub")).toBeNull();
  });

  it("drops failed courses from the average when asked to", async () => {
    serve({
      "GET /api/v1/me/grades": () =>
        json({
          items: [course("e1", "a", 5, 80, 2025, "fall"), course("e2", "b", 5, 40, 2025, "fall")],
        }),
    });
    wrap(<GpaPage />);

    expect(await screen.findByTestId("gpa-total")).toHaveTextContent("60.00");
    await userEvent.click(screen.getByRole("switch", { name: "Keçməyən fənləri say" }));
    expect(screen.getByTestId("gpa-total")).toHaveTextContent("80.00");
  });

  it("simulates new courses, ignoring an exam below the threshold, and shows the change", async () => {
    serve({ "GET /api/v1/me/grades": () => json({ items: TRANSCRIPT }) });
    wrap(<GpaPage />);
    await screen.findByTestId("gpa-total");

    await userEvent.click(screen.getByRole("button", { name: "Fənn əlavə et" }));
    await userEvent.clear(screen.getByLabelText("1-ci fənn: kredit"));
    await userEvent.type(screen.getByLabelText("1-ci fənn: kredit"), "10");
    await userEvent.clear(screen.getByLabelText("1-ci fənn: semestr balı (0–50)"));
    await userEvent.type(screen.getByLabelText("1-ci fənn: semestr balı (0–50)"), "40");
    await userEvent.clear(screen.getByLabelText("1-ci fənn: imtahan balı (0–50)"));
    await userEvent.type(screen.getByLabelText("1-ci fənn: imtahan balı (0–50)"), "50");

    expect(screen.getByTestId("gpa-simulated")).toHaveTextContent("81.08");
    expect(screen.getByTestId("gpa-delta")).toHaveTextContent("Dəyişiklik: +2.98");

    await userEvent.clear(screen.getByLabelText("1-ci fənn: imtahan balı (0–50)"));
    await userEvent.type(screen.getByLabelText("1-ci fənn: imtahan balı (0–50)"), "16");
    expect(screen.getByTestId("gpa-simulated")).toHaveTextContent("68.58");

    await userEvent.click(screen.getByRole("button", { name: "1-ci fənni sil" }));
    expect(screen.queryByTestId("gpa-simulated")).toBeNull();
  });

  it("says so when there is nothing graded yet and still offers the simulator", async () => {
    serve({ "GET /api/v1/me/grades": () => json({ items: [] }) });
    wrap(<GpaPage />);

    expect(await screen.findByText(/Hələ qiymətləndirilmiş fənniniz yoxdur/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Fənn əlavə et" })).toBeVisible();
  });
});

describe("remembered rules", () => {
  const MIXED = {
    items: [course("e1", "a", 5, 80, 2025, "fall"), course("e2", "b", 5, 40, 2025, "fall")],
  };
  const KEY = "smartazmiu:gpa-rules:v1";

  it("keeps a changed rule for the next visit and forgets it on reset", async () => {
    serve({ "GET /api/v1/me/grades": () => json(MIXED) });
    const first = wrap(<GpaPage />);
    expect(await screen.findByTestId("gpa-total")).toHaveTextContent("60.00");
    await userEvent.click(screen.getByRole("switch", { name: "Keçməyən fənləri say" }));
    expect(JSON.parse(window.localStorage.getItem(KEY)!)).toEqual({
      ...GPA_DEFAULTS,
      includeFailed: false,
    });
    first.unmount();

    wrap(<GpaPage />);
    await waitFor(() => expect(screen.getByTestId("gpa-total")).toHaveTextContent("80.00"));
    expect(screen.getByRole("switch", { name: "Keçməyən fənləri say" })).not.toBeChecked();

    await userEvent.click(screen.getByRole("button", { name: "Qaydaları sıfırla" }));
    expect(screen.getByTestId("gpa-total")).toHaveTextContent("60.00");
    expect(window.localStorage.getItem(KEY)).toBeNull();
  });

  it("ignores stored rules that are malformed or out of range", async () => {
    serve({ "GET /api/v1/me/grades": () => json(MIXED) });
    window.localStorage.setItem(KEY, JSON.stringify({ ...GPA_DEFAULTS, includeFailed: "no" }));
    wrap(<GpaPage />);
    expect(await screen.findByTestId("gpa-total")).toHaveTextContent("60.00");

    expect(parseRules({ ...GPA_DEFAULTS, roundDigits: 9 })).toBeNull();
    expect(parseRules({ ...GPA_DEFAULTS, passThreshold: 51.5 })).toBeNull();
    expect(parseRules({ ...GPA_DEFAULTS, retakePolicy: "newest" })).toBeNull();
    expect(parseRules(null)).toBeNull();
    expect(parseRules({ ...GPA_DEFAULTS })).toEqual(GPA_DEFAULTS);
  });

  it("works when the browser refuses to store anything", async () => {
    serve({ "GET /api/v1/me/grades": () => json(MIXED) });
    const refuse = () => {
      throw new DOMException("blocked", "SecurityError");
    };
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(refuse);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(refuse);
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(refuse);
    try {
      wrap(<GpaPage />);
      expect(await screen.findByTestId("gpa-total")).toHaveTextContent("60.00");
      await userEvent.click(screen.getByRole("switch", { name: "Keçməyən fənləri say" }));
      expect(screen.getByTestId("gpa-total")).toHaveTextContent("80.00");
    } finally {
      vi.restoreAllMocks();
    }
  });
});
