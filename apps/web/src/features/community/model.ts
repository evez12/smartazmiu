export type FeedPost = {
  id: string;
  author_id: string;
  author_name?: string;
  body: string;
  created_at: string;
  tags: string[];
  useful_count: number;
  comment_count: number;
  useful: boolean;
};

export type ForumQuestion = {
  id: string;
  title: string;
  body: string;
  excerpt?: string;
  author_id: string;
  author_name?: string;
  created_at: string;
  tags: string[];
  answer_count?: number;
  vote_count?: number;
  accepted?: boolean;
  teacher_verified?: boolean;
};

export type ForumAnswer = ForumQuestion & {
  body: string;
  author_role?: "student" | "teacher" | "guide";
};

export type QuestionDetail = ForumQuestion & { answers: ForumAnswer[] };

export type CommunityPage<T> = { items: T[]; next_cursor?: string | null };
