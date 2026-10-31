import type { components } from "@/lib/api/schema";

export type Tag = components["schemas"]["TagOut"];
export type FeedPost = components["schemas"]["PostOut"];
export type FeedComment = components["schemas"]["CommentOut"];
export type ForumQuestion = components["schemas"]["QuestionSummaryOut"];
export type QuestionDetail = components["schemas"]["QuestionDetailOut"];
export type ForumAnswer = components["schemas"]["AnswerOut"];
export type ContentKind = "post" | "comment" | "question" | "answer";

/** The most tags one post or question may carry (the API refuses more). */
export const MAX_TAGS = 5;
