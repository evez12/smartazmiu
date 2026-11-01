"use client";

import { useTranslations } from "next-intl";

import { AssignmentCard } from "@/features/assignments/assignments-list";
import { AssignmentInfo, MySubmission } from "@/features/assignments/assignment-detail";
import { CommentRow, PostCard } from "@/features/community/feed-page";
import { AnswerCard, QuestionCard } from "@/features/community/forum-pages";
import type {
  FeedComment,
  FeedPost,
  ForumAnswer,
  QuestionDetail,
} from "@/features/community/model";
import { QuizCard } from "@/features/quizzes/quizzes-list";
import { QuestionBlock, Result } from "@/features/quizzes/quiz-attempt";
import { ApiProvider } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";

import { Section } from "./section";

/*
 * Fixed data for the Sprint 12 and 13 screens, so `make visual` can compare them without an API: the same
 * components, the same copy, no network. Every id is made up and every time is fixed, so a run never changes.
 */

type Assignment = components["schemas"]["AssignmentDetailOut"];
type AssignmentSummary = components["schemas"]["AssignmentSummaryOut"];
type Quiz = components["schemas"]["QuizSummaryOut"];
type Question = components["schemas"]["QuestionOut"];

const NIGAR = {
  id: "11111111-aaaa-4a01-8a01-000000000001",
  display_name: "Nigar Hüseynova",
  photo_url: null,
  badge: null,
};
const RAUF = {
  id: "11111111-aaaa-4a01-8a01-000000000002",
  display_name: "Rauf Məmmədov",
  photo_url: null,
  badge: "teacher" as const,
};
const AYSEL = {
  id: "11111111-aaaa-4a01-8a01-000000000003",
  display_name: "Aysel Məmmədova",
  photo_url: null,
  badge: null,
};

const TAG = { id: "22222222-bbbb-4b02-8b02-000000000001", name: "Statistika", slug: "statistika" };
const TAG_EXAM = { id: "22222222-bbbb-4b02-8b02-000000000002", name: "İmtahan", slug: "imtahan" };

const POSTS: FeedPost[] = [
  {
    id: "33333333-cccc-4c03-8c03-000000000001",
    author: NIGAR,
    body: "Statistika üzrə konsultasiya cümə günü saat 14:00-da 2-204 otağında olacaq. Sualları əvvəlcədən qrup çatına yazın ki, vaxtında çatsın.",
    comment_count: 3,
    created_at: "2026-11-02T06:10:00Z",
    helpful_count: 12,
    hidden: false,
    mine: false,
    my_helpful: true,
    tags: [TAG, TAG_EXAM],
  },
  {
    id: "33333333-cccc-4c03-8c03-000000000002",
    author: AYSEL,
    body: "Keçən semestrin aralıq imtahan suallarını sinif yoldaşlarım üçün topladım. Fayl yalnız bitmiş semestrə aiddir.",
    comment_count: 0,
    created_at: "2026-11-01T17:45:00Z",
    helpful_count: 4,
    hidden: false,
    mine: true,
    my_helpful: false,
    tags: [],
  },
];

const COMMENT: FeedComment = {
  id: "44444444-dddd-4d04-8d04-000000000001",
  post_id: POSTS[0]!.id,
  author: RAUF,
  body: "Sualları əvvəlcədən göndərənlərin cavabına konsultasiyada ilk baxacağam.",
  created_at: "2026-11-02T07:02:00Z",
  hidden: false,
  mine: false,
};

const QUESTION_ID = "55555555-eeee-4e05-8e05-000000000001";
const ANSWERS: ForumAnswer[] = [
  {
    id: "66666666-ffff-4f06-8f06-000000000001",
    author: RAUF,
    body: "Seçmə ortanı hesablayanda kvartillər arasındakı məsafəni götürün. Sonra fərqi 1,5-ə vurub sərhədləri tapın.",
    accepted: true,
    created_at: "2026-11-02T08:20:00Z",
    hidden: false,
    mine: false,
    my_vote: 1,
    score: 7,
    verified_by: RAUF,
  },
  {
    id: "66666666-ffff-4f06-8f06-000000000002",
    author: NIGAR,
    body: "Mən də eyni üsulla etdim, amma sərhəddən kənar qiymətləri ayrıca qeyd etdim.",
    accepted: false,
    created_at: "2026-11-02T09:05:00Z",
    hidden: false,
    mine: false,
    my_vote: 0,
    score: 2,
    verified_by: null,
  },
];

const QUESTION: QuestionDetail = {
  id: QUESTION_ID,
  author: AYSEL,
  title: "Kənar qiymətləri necə müəyyən edək?",
  body: "Statistika dərsində verilən nümunədə kənar qiymətləri tapmaq lazımdır. Hansı düsturdan istifadə etməliyəm?",
  accepted_answer_id: ANSWERS[0]!.id,
  answers: ANSWERS,
  can_verify: true,
  created_at: "2026-11-02T07:40:00Z",
  hidden: false,
  mine: true,
  tags: [TAG],
  teacher_verified: true,
};

const OFFERING = {
  id: "77777777-1111-4111-8111-000000000001",
  subject_name: "Statistika",
  subject_code: "IQT-2102",
  groups: ["765a2"],
  semester: "2026 Payız",
};

const ASSIGNMENTS: AssignmentSummary[] = [
  {
    id: "88888888-2222-4222-8222-000000000001",
    title: "Reqressiya təhlili üzrə hesabat",
    offering: OFFERING,
    deadline: "2026-11-09T19:59:00Z",
    available_from: null,
    max_points: "10",
    late_policy: "penalize",
    late_penalty_percent: "20",
    can_manage: false,
    my_status: "submitted",
    enrolled_count: null,
    submitted_count: null,
    graded_count: null,
  },
  {
    id: "88888888-2222-4222-8222-000000000002",
    title: "Seçmə üsullarına dair ev tapşırığı",
    offering: OFFERING,
    deadline: "2026-11-16T19:59:00Z",
    available_from: null,
    max_points: "5",
    late_policy: "accept",
    late_penalty_percent: "0",
    can_manage: true,
    my_status: null,
    enrolled_count: 28,
    submitted_count: 19,
    graded_count: 11,
  },
];

const ASSIGNMENT: Assignment = {
  ...ASSIGNMENTS[0]!,
  instructions:
    "Verilmiş məlumat dəstində xətti reqressiya qurun, qalıqların qrafikini əlavə edin və nəticəni bir səhifədə şərh edin.",
  can_submit: false,
  submit_blocked: null,
  my_status: "graded",
  my_submission: {
    id: "99999999-3333-4333-8333-000000000001",
    submitted_at: "2026-11-10T07:30:00Z",
    is_late: true,
    files: [
      {
        id: "99999999-3333-4333-8333-000000000011",
        filename: "reqressiya-hesabat-v2.pdf",
        mime: "application/pdf",
        previewable: true,
        size_bytes: 1_835_008,
        status: "clean",
        version: 2,
        created_at: "2026-11-10T07:30:00Z",
      },
      {
        id: "99999999-3333-4333-8333-000000000012",
        filename: "reqressiya-hesabat.docx",
        mime: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        previewable: false,
        size_bytes: 412_672,
        status: "infected",
        version: 1,
        created_at: "2026-11-09T18:10:00Z",
      },
    ],
    grade: {
      points: "6.4",
      raw_points: "8",
      feedback: "Qalıqların təhlili yaxşıdır. Nəticə hissəsini daha qısa yazın.",
      graded_at: "2026-11-12T09:00:00Z",
    },
  },
};

const QUIZZES: Quiz[] = [
  {
    id: "aaaaaaaa-4444-4444-8444-000000000001",
    title: "Ehtimal paylanmaları: yoxlama testi",
    offering: OFFERING,
    question_count: 12,
    time_limit_seconds: 1800,
    max_attempts: 2,
    deadline: "2026-11-20T19:59:00Z",
    available_from: null,
    can_manage: false,
    published: true,
    attempts_used: 1,
    best_percent: 75,
    students_attempted: null,
  },
  {
    id: "aaaaaaaa-4444-4444-8444-000000000002",
    title: "Seçmə nəzəriyyəsi",
    offering: OFFERING,
    question_count: 8,
    time_limit_seconds: null,
    max_attempts: 3,
    deadline: null,
    available_from: "2026-11-23T05:00:00Z",
    can_manage: true,
    published: false,
    attempts_used: null,
    best_percent: null,
    students_attempted: 0,
  },
];

const QUESTIONS: Question[] = [
  {
    id: "bbbbbbbb-5555-4555-8555-000000000001",
    position: 1,
    type: "mcq",
    prompt: "Normal paylanmada orta və median bir-birinə necə münasibətdədir?",
    points: 2,
    is_required: true,
    options: [
      { id: "bbbbbbbb-5555-4555-8555-0000000000a1", text: "Bərabərdir" },
      { id: "bbbbbbbb-5555-4555-8555-0000000000a2", text: "Orta medianın sağındadır" },
      { id: "bbbbbbbb-5555-4555-8555-0000000000a3", text: "Orta medianın solundadır" },
    ],
  },
  {
    id: "bbbbbbbb-5555-4555-8555-000000000002",
    position: 2,
    type: "multi_select",
    prompt: "Hansı göstəricilər yayılmanı ölçür?",
    points: 3,
    is_required: true,
    options: [
      { id: "bbbbbbbb-5555-4555-8555-0000000000b1", text: "Standart sapma" },
      { id: "bbbbbbbb-5555-4555-8555-0000000000b2", text: "Moda" },
      { id: "bbbbbbbb-5555-4555-8555-0000000000b3", text: "Variasiya genişliyi" },
    ],
  },
  {
    id: "bbbbbbbb-5555-4555-8555-000000000003",
    position: 3,
    type: "short_answer",
    prompt: "Seçmənin ölçüsü artdıqda standart xəta necə dəyişir?",
    points: 5,
    is_required: false,
    options: [],
  },
];

const RESULT: components["schemas"]["AttemptOut"] = {
  id: "cccccccc-6666-4666-8666-000000000001",
  quiz_id: QUIZZES[0]!.id,
  attempt_number: 1,
  status: "submitted",
  started_at: "2026-11-05T08:00:00Z",
  submitted_at: "2026-11-05T08:21:00Z",
  expires_at: null,
  server_time: "2026-11-05T08:21:00Z",
  score: 7.5,
  max_score: 10,
  pending_review: true,
  answers: {},
  questions: null,
};

const noop = () => undefined;

export function Sprint1213Specimens() {
  const t = useTranslations("designSystem.sections");
  return (
    <ApiProvider csrfToken="specimen">
      <Section title={t("feedPosts")}>
        <div className="flex flex-col gap-3">
          {POSTS.map((post) => (
            <PostCard key={post.id} post={post} canModerate={false} />
          ))}
          <CommentRow comment={COMMENT} canModerate={false} />
        </div>
      </Section>
      <Section title={t("forumQuestions")}>
        <div className="flex flex-col gap-3">
          <QuestionCard
            question={{
              ...QUESTION,
              excerpt: QUESTION.body,
              answer_count: ANSWERS.length,
              accepted: true,
            }}
          />
          <QuestionCard
            question={{
              ...QUESTION,
              id: "55555555-eeee-4e05-8e05-000000000002",
              title: "Aralıq imtahanda hansı mövzular çıxacaq?",
              excerpt: "Müəllim bu barədə dərsdə danışmışdı, amma qeydlərimdə yazılmayıb.",
              answer_count: 0,
              accepted: false,
              teacher_verified: false,
              mine: false,
              author: NIGAR,
              tags: [TAG, TAG_EXAM],
            }}
          />
        </div>
      </Section>
      <Section title={t("forumAnswers")}>
        <div className="flex flex-col gap-3">
          {ANSWERS.map((answer) => (
            <AnswerCard key={answer.id} answer={answer} question={QUESTION} canModerate={false} />
          ))}
        </div>
      </Section>
      <Section title={t("assignmentCards")}>
        <div className="flex flex-col gap-3">
          {ASSIGNMENTS.map((item) => (
            <AssignmentCard key={item.id} item={item} />
          ))}
        </div>
      </Section>
      <Section title={t("assignmentSubmission")}>
        <AssignmentInfo assignment={ASSIGNMENT} />
        <MySubmission assignment={ASSIGNMENT} />
      </Section>
      <Section title={t("quizCards")}>
        <div className="flex flex-col gap-3">
          {QUIZZES.map((quiz) => (
            <QuizCard key={quiz.id} quiz={quiz} />
          ))}
        </div>
      </Section>
      <Section title={t("quizAttempt")}>
        <div className="flex flex-col gap-3">
          <QuestionBlock
            question={QUESTIONS[0]!}
            number={1}
            total={3}
            value={QUESTIONS[0]!.options[0]!.id}
            onChange={noop}
          />
          <QuestionBlock
            question={QUESTIONS[1]!}
            number={2}
            total={3}
            value={[QUESTIONS[1]!.options[0]!.id, QUESTIONS[1]!.options[2]!.id]}
            onChange={noop}
          />
          <QuestionBlock
            question={QUESTIONS[2]!}
            number={3}
            total={3}
            value="Seçmənin ölçüsü artdıqca standart xəta azalır."
            onChange={noop}
          />
          <Result attempt={RESULT} quizId={QUIZZES[0]!.id} />
        </div>
      </Section>
    </ApiProvider>
  );
}
