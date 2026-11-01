import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { ApiProvider } from "@/lib/api/provider";
import { fetchMock, json, serve } from "@/test/api";
import { renderWithIntl } from "@/test/render";

import { QuizAttemptPage, Result } from "./quiz-attempt";
import { QuizPage } from "./quiz-detail";
import { QuizResults } from "./quiz-results";
import { QuizReview } from "./quiz-review";
import { QuizzesPage } from "./quizzes-list";

const router = { refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => "/quizzes" }));

beforeEach(() => vi.stubGlobal("fetch", fetchMock));
afterEach(() => {
  vi.useRealTimers();
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

const OFFERING = {
  id: "o-1",
  subject_name: "Statistika",
  subject_code: "IQT-2102",
  groups: ["765a2"],
  semester: "2026 Payız",
};
const QUIZ = {
  id: "q-1",
  offering: OFFERING,
  title: "Aralıq test",
  available_from: null,
  deadline: null,
  time_limit_seconds: 1200,
  max_attempts: 2,
  published: true,
  question_count: 3,
  can_manage: false,
  attempts_used: 0,
  best_percent: null,
  students_attempted: null,
};
const STUDENT_DETAIL = {
  ...QUIZ,
  instructions: "Kalkulyatordan istifadə etmək olar.",
  can_start: true,
  start_blocked: null,
  my_attempts: [],
  questions: null,
};
const QUESTIONS = [
  {
    id: "k-1",
    position: 1,
    type: "mcq",
    prompt: "Medianın tərifi hansıdır?",
    points: 2,
    options: [
      { id: "a", text: "Orta qiymət" },
      { id: "b", text: "Ortadakı qiymət" },
    ],
    is_required: true,
  },
  {
    id: "k-2",
    position: 2,
    type: "multi_select",
    prompt: "Mərkəzi meyl göstəricilərini seçin.",
    points: 3,
    options: [
      { id: "a", text: "Orta" },
      { id: "b", text: "Dispersiya" },
      { id: "c", text: "Median" },
    ],
    is_required: true,
  },
  {
    id: "k-3",
    position: 3,
    type: "short_answer",
    prompt: "Normal paylanmanı izah edin.",
    points: 5,
    options: [],
    is_required: true,
  },
];
const ATTEMPT = {
  id: "t-1",
  attempt_number: 1,
  status: "in_progress",
  started_at: "2026-11-02T08:00:00Z",
  submitted_at: null,
  score: null,
  max_score: null,
  pending_review: false,
  quiz_id: "q-1",
  expires_at: null,
  answers: {},
  questions: QUESTIONS,
  server_time: "2026-11-02T08:00:00Z",
};

describe("the student's quiz page", () => {
  it("starts an attempt and goes to it; a resumed one says so", async () => {
    serve({
      "GET /api/v1/quizzes/q-1": () => json(STUDENT_DETAIL),
      "POST /api/v1/quizzes/q-1/attempts": () => json(ATTEMPT, 201),
    });
    wrap(<QuizPage id="q-1" />);
    await screen.findByText("Kalkulyatordan istifadə etmək olar.");
    expect(screen.getByText("3 sual")).toBeVisible();
    expect(screen.getByText("20 dəqiqə")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Testə başlayın" }));
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/quizzes/q-1/attempt/t-1"));
  });

  it("shows past attempts with the score, the pending marker, and why a new one cannot start", async () => {
    serve({
      "GET /api/v1/quizzes/q-1": () =>
        json({
          ...STUDENT_DETAIL,
          can_start: false,
          start_blocked: "attempt_limit_reached",
          my_attempts: [
            { ...ATTEMPT, status: "submitted", score: 5, max_score: 10, pending_review: true },
          ],
        }),
    });
    wrap(<QuizPage id="q-1" />);
    expect(await screen.findByText("5 / 10 bal")).toBeVisible();
    expect(screen.getByText("Açıq suallar müəllim tərəfindən qiymətləndirilir.")).toBeVisible();
    expect(screen.getByText("Cəhd sayınız bitib.")).toBeVisible();
    expect(screen.queryByRole("button", { name: /Testə başlayın|davam/ })).toBeNull();
  });
});

describe("the teacher's quiz page", () => {
  const draft = {
    ...STUDENT_DETAIL,
    published: false,
    can_manage: true,
    attempts_used: null,
    students_attempted: 0,
    can_start: false,
    questions: [
      { ...QUESTIONS[0], correct_answer: "b" },
      { ...QUESTIONS[1], correct_answer: ["a", "c"] },
    ],
  };

  it("shows the correct answers to the teacher and checks a new question before sending it", async () => {
    let added: Request | null = null;
    serve({
      "GET /api/v1/quizzes/q-1": () => json(draft),
      "POST /api/v1/quizzes/q-1/questions": (request) => {
        added = request.clone();
        return json(draft, 201);
      },
    });
    wrap(<QuizPage id="q-1" />);
    const first = (await screen.findByText(/Medianın tərifi/)).closest("article")!;
    expect(within(first).getByText("Düzgün cavab")).toBeVisible();
    expect(within(first).getByText("Ortadakı qiymət")).toBeVisible();
    expect(screen.getByText("Qaralama")).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: "Sualı əlavə edin" }));
    expect(screen.getByText("Sualın mətnini yazın.")).toBeVisible();
    expect(screen.getByText("Ən azı iki variantı doldurun.")).toBeVisible();
    expect(screen.getByText("Düzgün cavabı seçin.")).toBeVisible();
    expect(added).toBeNull();

    await userEvent.type(screen.getByLabelText(/Sualın mətni/), "Variasiya genişliyi nədir?");
    await userEvent.type(screen.getByLabelText("Variant 1"), "Maksimum minus minimum");
    await userEvent.type(screen.getByLabelText("Variant 2"), "Orta qiymət");
    await userEvent.click(screen.getByRole("checkbox", { name: "1-ci variant düzgündür" }));
    await userEvent.click(screen.getByRole("button", { name: "Sualı əlavə edin" }));
    await waitFor(() => expect(added).not.toBeNull());
    expect(await (added as unknown as Request).json()).toEqual({
      type: "mcq",
      prompt: "Variasiya genişliyi nədir?",
      points: 1,
      is_required: true,
      options: [
        { id: "a", text: "Maksimum minus minimum" },
        { id: "b", text: "Orta qiymət" },
      ],
      correct_answer: "a",
    });
  });

  it("publishes only after the consequence is confirmed and not an empty quiz", async () => {
    let published = false;
    serve({
      "GET /api/v1/quizzes/q-1": () => json(draft),
      "POST /api/v1/quizzes/q-1/publish": () => {
        published = true;
        return json({ ...draft, published: true });
      },
    });
    wrap(<QuizPage id="q-1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Testi dərc edin" }));
    expect(published).toBe(false);
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByText(/Dərc olunandan sonra suallar dəyişmir/)).toBeVisible();
    await userEvent.click(within(dialog).getByRole("button", { name: "Testi dərc edin" }));
    await waitFor(() => expect(published).toBe(true));
  });

  it("disables publishing while there are no questions", async () => {
    serve({ "GET /api/v1/quizzes/q-1": () => json({ ...draft, questions: [] }) });
    wrap(<QuizPage id="q-1" />);
    expect(await screen.findByRole("button", { name: "Testi dərc edin" })).toBeDisabled();
    expect(screen.getByText("Dərc etmək üçün ən azı bir sual əlavə edin.")).toBeVisible();
  });
});

describe("taking an attempt", () => {
  it("shows the questions without any correct answer and saves answers a moment after typing", async () => {
    let saved: Request | null = null;
    serve({
      "GET /api/v1/quiz-attempts/t-1": () => json(ATTEMPT),
      "PATCH /api/v1/quiz-attempts/t-1": (request) => {
        saved = request.clone();
        return json(ATTEMPT);
      },
    });
    wrap(<QuizAttemptPage quizId="q-1" attemptId="t-1" />);
    await screen.findByText("Medianın tərifi hansıdır?");
    expect(screen.getByText("Vaxt məhdudiyyəti yoxdur")).toBeVisible();
    expect(screen.getByText("Sual 2 / 3")).toBeVisible();
    await userEvent.click(screen.getByRole("radio", { name: "Ortadakı qiymət" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Median" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Orta" }));
    await waitFor(() => expect(saved).not.toBeNull(), { timeout: 4000 });
    expect(await (saved as unknown as Request).json()).toEqual({
      answers: { "k-1": "b", "k-2": ["c", "a"] },
    });
    expect(await screen.findByText("Cavablar yadda saxlanıb.")).toBeVisible();
  });

  it("counts down from the server's clock, not the device's", async () => {
    vi.useFakeTimers({ toFake: ["Date", "setInterval", "clearInterval"] });
    vi.setSystemTime(new Date("2030-01-01T00:00:00Z"));
    // The server says it is 08:00:00 and the time ends at 08:01:30, whatever this device thinks.
    serve({
      "GET /api/v1/quiz-attempts/t-1": () =>
        json({
          ...ATTEMPT,
          expires_at: "2026-11-02T08:01:30Z",
          server_time: "2026-11-02T08:00:00Z",
        }),
    });
    wrap(<QuizAttemptPage quizId="q-1" attemptId="t-1" />);
    await vi.waitFor(() =>
      expect(screen.getByRole("timer")).toHaveTextContent("Qalan vaxt: 01:30"),
    );
    await vi.advanceTimersByTimeAsync(30_000);
    expect(screen.getByRole("timer")).toHaveTextContent("Qalan vaxt: 01:00");
  });

  it("asks for confirmation, names the unanswered questions, then shows the result", async () => {
    let sent: Request | null = null;
    serve({
      "GET /api/v1/quiz-attempts/t-1": () => json(ATTEMPT),
      "POST /api/v1/quiz-attempts/t-1/submit": (request) => {
        sent = request.clone();
        return json({
          ...ATTEMPT,
          status: "submitted",
          score: 5,
          max_score: 10,
          pending_review: true,
          questions: null,
          submitted_at: "2026-11-02T08:10:00Z",
        });
      },
    });
    wrap(<QuizAttemptPage quizId="q-1" attemptId="t-1" />);
    await userEvent.click(await screen.findByRole("radio", { name: "Ortadakı qiymət" }));
    await userEvent.click(screen.getByRole("button", { name: "Testi bitirin" }));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByText(/2 sual cavabsızdır/)).toBeVisible();
    expect(sent).toBeNull();
    await userEvent.click(within(dialog).getByRole("button", { name: "Testi bitirin" }));
    expect(await screen.findByText("5 / 10 bal · 50%")).toBeVisible();
    expect(screen.getByText("Test göndərilib")).toBeVisible();
    expect(
      screen.getByText("Açıq suallar hələ qiymətləndirilməyib. Bal dəyişə bilər."),
    ).toBeVisible();
    expect(await (sent as unknown as Request).json()).toEqual({ answers: { "k-1": "b" } });
  });

  it("shows the result of a finished attempt, with the automatic submission explained", async () => {
    serve({
      "GET /api/v1/quiz-attempts/t-1": () =>
        json({
          ...ATTEMPT,
          status: "auto_submitted",
          score: 10,
          max_score: 10,
          questions: null,
        }),
    });
    wrap(<QuizAttemptPage quizId="q-1" attemptId="t-1" />);
    expect(await screen.findByText("Vaxt bitdiyi üçün test avtomatik göndərilib")).toBeVisible();
    expect(screen.getByText("10 / 10 bal · 100%")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Testi bitirin" })).toBeNull();
  });
});

describe("the list", () => {
  it("shows a student their attempts and best result", async () => {
    serve({
      "GET /api/v1/quizzes": () =>
        json({ items: [{ ...QUIZ, attempts_used: 1, best_percent: 80 }] }),
      "GET /api/v1/coursework/offerings": () => json({ items: [] }),
    });
    wrap(<QuizzesPage />);
    const card = (await screen.findByRole("link", { name: "Aralıq test" })).closest("article")!;
    expect(within(card).getByText("Cəhdlər: 1 / 2")).toBeVisible();
    expect(within(card).getByText("Ən yaxşı nəticə: 80%")).toBeVisible();
    expect(screen.queryByRole("link", { name: "Test yaradın" })).toBeNull();
  });
});

describe("results and review", () => {
  it("shows the statistics and which attempts still wait for a teacher's points", async () => {
    serve({
      "GET /api/v1/quizzes/q-1/stats": () =>
        json({
          submitted_attempts: 4,
          students: 3,
          average_percent: 72,
          pending_review: 1,
          distribution: [
            { label: "0–50", count: 1 },
            { label: "51–70", count: 1 },
            { label: "71–90", count: 2 },
            { label: "91–100", count: 0 },
          ],
          questions: [
            {
              question_id: "k-1",
              position: 1,
              prompt: "Medianın tərifi",
              type: "mcq",
              correct_percent: 75,
            },
            {
              question_id: "k-3",
              position: 3,
              prompt: "Normal paylanma",
              type: "short_answer",
              correct_percent: null,
            },
          ],
        }),
      "GET /api/v1/quizzes/q-1/attempts": () =>
        json({
          items: [
            {
              ...ATTEMPT,
              status: "submitted",
              score: 5,
              max_score: 10,
              pending_review: true,
              submitted_at: "2026-11-02T08:10:00Z",
              student: { id: "u-1", display_name: "Aysel Məmmədova", group_code: "765a2" },
            },
          ],
        }),
    });
    wrap(<QuizResults quizId="q-1" />);
    expect(await screen.findByText("72%")).toBeVisible();
    expect(screen.getByText("75% düzgün")).toBeVisible();
    expect(screen.getByText("Açıq sual")).toBeVisible();
    const row = (await screen.findByText("Aysel Məmmədova")).closest("tr")!;
    expect(within(row).getByText("Açıq suallar gözləyir")).toBeVisible();
    expect(within(row).getByRole("link", { name: "Baxın" })).toHaveAttribute(
      "href",
      "/quizzes/q-1/results/t-1",
    );
  });

  it("scores an open question within its points and sends only what was typed", async () => {
    let scored: Request | null = null;
    const review = {
      ...ATTEMPT,
      status: "submitted",
      score: 5,
      max_score: 10,
      pending_review: true,
      student: { id: "u-1", display_name: "Aysel Məmmədova", group_code: "765a2" },
      answers: { "k-1": "b", "k-3": "Zəng əyrisi" },
      manual_scores: {},
      questions: [
        { ...QUESTIONS[0], correct_answer: "b" },
        { ...QUESTIONS[2], correct_answer: null },
      ],
    };
    serve({
      "GET /api/v1/quiz-attempts/t-1/review": () => json(review),
      "PUT /api/v1/quiz-attempts/t-1/open-question-scores": (request) => {
        scored = request.clone();
        return json(review);
      },
    });
    wrap(<QuizReview quizId="q-1" attemptId="t-1" />);
    expect(await screen.findByText("Zəng əyrisi")).toBeVisible();
    expect(screen.getByText("Düzgündür")).toBeVisible();
    const score = screen.getByLabelText("Bal (0–5)");
    await userEvent.type(score, "9");
    await userEvent.click(screen.getByRole("button", { name: "Balları yadda saxlayın" }));
    expect(screen.getByText("0 ilə 5 arasında bal yazın.")).toBeVisible();
    expect(scored).toBeNull();
    await userEvent.clear(score);
    await userEvent.type(score, "4");
    await userEvent.click(screen.getByRole("button", { name: "Balları yadda saxlayın" }));
    await waitFor(() => expect(scored).not.toBeNull());
    expect(await (scored as unknown as Request).json()).toEqual({ scores: { "k-3": 4 } });
  });
});

describe("scores", () => {
  it("are written with a decimal comma, like assignment grades", () => {
    wrap(
      <Result
        quizId="q-1"
        attempt={{
          id: "a-1",
          quiz_id: "q-1",
          attempt_number: 1,
          status: "submitted",
          started_at: "2027-01-10T08:00:00Z",
          submitted_at: "2027-01-10T08:20:00Z",
          expires_at: null,
          server_time: "2027-01-10T08:20:00Z",
          score: 7.5,
          max_score: 10,
          pending_review: false,
          answers: {},
          questions: null,
        }}
      />,
    );
    expect(screen.getByText(/7,5 \/ 10 bal/)).toBeVisible();
  });
});
