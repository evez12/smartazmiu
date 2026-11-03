import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { ApiProvider } from "@/lib/api/provider";
import { fetchMock, json, serve } from "@/test/api";
import { renderWithIntl } from "@/test/render";

import { FeedPage } from "./feed-page";
import { QuestionPage, QuestionsPage } from "./forum-pages";

const router = { refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => "/feed" }));

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

// The provider retries a failed query once before showing the error state.
const RETRY_WAIT = { timeout: 4000 };

const TAGS = { items: [{ id: "t-1", slug: "kitabxana", name: "Kitabxana" }] };
const AUTHOR = { id: "u-1", display_name: "Aysel Məmmədova", photo_url: null, badge: null };

const post = {
  id: "p-1",
  author: AUTHOR,
  body: "Kitabxana şənbə günü də açıqdır.",
  tags: TAGS.items,
  helpful_count: 2,
  comment_count: 1,
  my_helpful: false,
  mine: false,
  hidden: false,
  created_at: "2026-10-27T08:00:00Z",
};

describe("feed", () => {
  it("shows posts with the author, tags and counts, and a composer", async () => {
    serve({
      "GET /api/v1/feed/posts": () => json({ items: [post], next_cursor: null }),
      "GET /api/v1/community/tags": () => json(TAGS),
    });
    wrap(<FeedPage canModerate={false} />);
    expect(await screen.findByText("Kitabxana şənbə günü də açıqdır.")).toBeVisible();
    expect(screen.getAllByText("Aysel Məmmədova").length).toBeGreaterThan(0);
    expect(screen.getByRole("textbox", { name: /Yeni paylaşım/ })).toBeVisible();
    expect(screen.getByRole("button", { name: /Faydalıdır/ })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByRole("button", { name: "Şikayət edin" })).toBeVisible();
  });

  it("offers delete instead of report on your own post, and hide to staff", async () => {
    serve({
      "GET /api/v1/feed/posts": () => json({ items: [{ ...post, mine: true }], next_cursor: null }),
      "GET /api/v1/community/tags": () => json(TAGS),
    });
    wrap(<FeedPage canModerate />);
    await screen.findByText(post.body);
    expect(screen.getByRole("button", { name: "Silin" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Şikayət edin" })).toBeNull();
    expect(screen.getByRole("button", { name: "Gizlədin" })).toBeVisible();
    // Your own post has no "helpful" button: the API refuses it (D-090).
    expect(screen.queryByRole("button", { name: /Faydalıdır/ })).toBeNull();
  });

  it("publishes a post with an idempotency key and refuses an empty one", async () => {
    let created: Request | null = null;
    serve({
      "GET /api/v1/feed/posts": () => json({ items: [], next_cursor: null }),
      "GET /api/v1/community/tags": () => json(TAGS),
      "POST /api/v1/feed/posts": (request) => {
        created = request.clone();
        return json({ ...post, mine: true }, 201);
      },
    });
    wrap(<FeedPage canModerate={false} />);
    await userEvent.click(await screen.findByRole("button", { name: "Paylaşın" }));
    expect(screen.getByText("Paylaşımın mətnini yazın.")).toBeVisible();
    expect(created).toBeNull();

    await userEvent.type(screen.getByRole("textbox", { name: /Yeni paylaşım/ }), "Salam");
    await userEvent.click(screen.getByRole("checkbox", { name: "Kitabxana" }));
    await userEvent.click(screen.getByRole("button", { name: "Paylaşın" }));
    await waitFor(() => expect(created).not.toBeNull());
    const request = created as unknown as Request;
    expect(request.headers.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
    expect(await request.json()).toEqual({ body: "Salam", tag_ids: ["t-1"] });
  });

  it("shows the explanatory empty state, and a retry when loading fails", async () => {
    serve({
      "GET /api/v1/feed/posts": () => json({ items: [], next_cursor: null }),
      "GET /api/v1/community/tags": () => json(TAGS),
    });
    const { unmount } = wrap(<FeedPage canModerate={false} />);
    expect(await screen.findByText(/Hələ heç bir paylaşım yoxdur/)).toBeVisible();
    unmount();

    serve({
      "GET /api/v1/feed/posts": () => json({ error: { code: "x", message: "x" } }, 500),
      "GET /api/v1/community/tags": () => json(TAGS),
    });
    wrap(<FeedPage canModerate={false} />);
    expect(
      await screen.findByRole("button", { name: "Yenidən cəhd edin" }, RETRY_WAIT),
    ).toBeVisible();
  });
});

describe("a refused list", () => {
  const refused = () => json({ error: { code: "auth.forbidden", message: "x" } }, 403);

  it("shows the forbidden state, not the retry button, for the feed", async () => {
    serve({ "GET /api/v1/feed/posts": refused, "GET /api/v1/community/tags": () => json(TAGS) });
    wrap(<FeedPage canModerate={false} />);

    expect(
      await screen.findByRole("heading", { name: /icazəniz yoxdur/ }, RETRY_WAIT),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "Yenidən cəhd edin" })).not.toBeInTheDocument();
  });

  it("shows the forbidden state for the forum questions", async () => {
    serve({
      "GET /api/v1/forum/questions": refused,
      "GET /api/v1/community/tags": () => json(TAGS),
    });
    wrap(<QuestionsPage />);

    expect(
      await screen.findByRole("heading", { name: /icazəniz yoxdur/ }, RETRY_WAIT),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "Yenidən cəhd edin" })).not.toBeInTheDocument();
  });
});

const question = {
  id: "q-1",
  author: AUTHOR,
  title: "Statistika imtahanında kalkulyator olar?",
  excerpt: "Keçən il icazə verilirdi.",
  tags: [],
  answer_count: 2,
  accepted: true,
  teacher_verified: true,
  mine: false,
  hidden: false,
  created_at: "2026-10-27T08:00:00Z",
};

describe("forum", () => {
  it("lists questions with the answer count and the accepted and verified marks", async () => {
    serve({
      "GET /api/v1/forum/questions": () => json({ items: [question], next_cursor: null }),
      "GET /api/v1/community/tags": () => json(TAGS),
    });
    wrap(<QuestionsPage />);
    const link = await screen.findByRole("link", { name: question.title });
    expect(link).toHaveAttribute("href", "/forum/questions/q-1");
    expect(screen.getByText("2 cavab")).toBeVisible();
    expect(screen.getByText("Qəbul edilmiş cavab")).toBeVisible();
    expect(screen.getByText("Müəllim təsdiqləyib")).toBeVisible();
  });

  const detail = {
    ...question,
    body: "Keçən il icazə verilirdi.",
    accepted_answer_id: "a-1",
    can_verify: true,
    answers: [
      {
        id: "a-1",
        author: { ...AUTHOR, id: "u-2", display_name: "Ramin Əliyev" },
        body: "Bəli, sadə kalkulyator olar.",
        score: 3,
        my_vote: 1,
        accepted: true,
        verified_by: { ...AUTHOR, id: "u-3", display_name: "Leyla Həsənova" },
        mine: false,
        hidden: false,
        created_at: "2026-10-27T09:00:00Z",
      },
    ],
  };

  it("shows answers with votes, the verifier, and only the actions your role allows", async () => {
    serve({ "GET /api/v1/forum/questions/q-1": () => json({ ...detail, mine: true }) });
    wrap(<QuestionPage id="q-1" canModerate={false} />);
    const answer = (await screen.findByText("Bəli, sadə kalkulyator olar.")).closest("article")!;
    expect(within(answer).getByText("Leyla Həsənova təsdiqləyib")).toBeVisible();
    expect(within(answer).getByRole("button", { name: "Faydalı cavab" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    // The question's author accepts; a teacher or staff verifies.
    expect(within(answer).getByRole("button", { name: "Qəbulu ləğv edin" })).toBeVisible();
    expect(within(answer).getByRole("button", { name: "Təsdiqi götürün" })).toBeVisible();
    // Exactly one top-level heading belongs to the page header, not to the question.
    expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
  });

  it("hides accept and verify from people who may not use them, and votes once per click", async () => {
    let vote: Request | null = null;
    serve({
      "GET /api/v1/forum/questions/q-1": () =>
        json({ ...detail, can_verify: false, answers: [{ ...detail.answers[0], my_vote: 0 }] }),
      "PUT /api/v1/forum/answers/a-1/vote": (request) => {
        vote = request.clone();
        return new Response(null, { status: 204 });
      },
    });
    wrap(<QuestionPage id="q-1" canModerate={false} />);
    await screen.findByText("Bəli, sadə kalkulyator olar.");
    expect(screen.queryByRole("button", { name: "Cavabı qəbul edin" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Cavabı təsdiqləyin" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Faydalı cavab" }));
    await waitFor(() => expect(vote).not.toBeNull());
    expect(new URL((vote as unknown as Request).url).searchParams.get("value")).toBe("1");
  });

  it("shows a not-found style error for a hidden or deleted question", async () => {
    serve({
      "GET /api/v1/forum/questions/q-9": () =>
        json({ error: { code: "community.question_not_found", message: "x" } }, 404),
    });
    wrap(<QuestionPage id="q-9" canModerate={false} />);
    expect(
      await screen.findByRole("button", { name: "Yenidən cəhd edin" }, RETRY_WAIT),
    ).toBeVisible();
  });
});
