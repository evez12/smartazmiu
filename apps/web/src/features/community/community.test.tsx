import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithIntl } from "@/test/render";

import { FeedPage, QuestionsPage } from "./community-pages";

const fetchMock = vi.fn();

afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

function renderQuery(ui: React.ReactNode) {
  return renderWithIntl(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      {ui}
    </QueryClientProvider>,
  );
}

describe("community pages", () => {
  it("renders feed posts from the typed endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      fetchMock.mockResolvedValue(
        new Response(
          JSON.stringify({
            items: [
              {
                id: "p-1",
                author_id: "u-1",
                author_name: "Aysel Məmmədli",
                body: "İmtahan materialını paylaşdım.",
                created_at: "2026-10-27T12:00:00Z",
                tags: ["riyaziyyat"],
                useful_count: 2,
                comment_count: 1,
                useful: false,
              },
            ],
          }),
          { status: 200 },
        ),
      ),
    );
    renderQuery(<FeedPage />);
    expect(await screen.findByText("İmtahan materialını paylaşdım.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/feed/posts",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("shows a clear empty state for questions", async () => {
    vi.stubGlobal(
      "fetch",
      fetchMock.mockResolvedValue(new Response(JSON.stringify({ items: [] }), { status: 200 })),
    );
    renderQuery(<QuestionsPage />);
    await waitFor(() => expect(screen.getByText(/payla/i)).toBeInTheDocument());
  });
});
