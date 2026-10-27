import type { CommunityPage, FeedPost, ForumQuestion, QuestionDetail } from "./model";

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    headers: { Accept: "application/json", "Accept-Language": "az" },
    credentials: "include",
  });
  if (!response.ok) {
    const error = new Error("community.requestFailed") as Error & { status?: number };
    error.status = response.status;
    throw error;
  }
  return (await response.json()) as T;
}

/** Typed community client. The endpoints are kept here until the OpenAPI contract is published. */
export const communityApi = {
  feed: () => get<CommunityPage<FeedPost>>("/feed/posts"),
  questions: (tag?: string) =>
    get<CommunityPage<ForumQuestion>>(
      `/forum/questions${tag ? `?tag=${encodeURIComponent(tag)}` : ""}`,
    ),
  question: (id: string) => get<QuestionDetail>(`/forum/questions/${encodeURIComponent(id)}`),
  tag: (tag: string) => get<CommunityPage<ForumQuestion>>(`/forum/tags/${encodeURIComponent(tag)}`),
};
