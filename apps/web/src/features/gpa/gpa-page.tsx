"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useId, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { RadioGroup, Switch } from "@/components/ui/choice";
import { Field, Input, Select } from "@/components/ui/field";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tag } from "@/components/ui/tag";
import { CabinetCard } from "@/features/cabinet/cabinet-card";
import { ScreenState } from "@/features/coursework/coursework";
import { unwrap } from "@/lib/api/browser";
import { useApi } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";

import { semesterResults, simulate, type Draft, type SemesterResult } from "./model";
import { loadRules, saveRules } from "./rules-storage";
import {
  earnedCredits,
  GPA_DEFAULTS,
  letterGrade,
  NO_LOAN_INTEREST_FROM,
  TOP_TIER_FROM,
  uomg,
  type GpaConfig,
} from "./uomg";

type Grade = components["schemas"]["FinishedCourseOut"];

/** The student's cumulative and per-semester ÜOMG from their own results, with the rules and a what-if simulator. */
export function GpaPage() {
  const t = useTranslations("gpa");
  const api = useApi();
  const [config, setConfig] = useState<GpaConfig>(GPA_DEFAULTS);
  // Read after mount, so the server render and the first client render agree (the rules are a per-viewer extra).
  useEffect(() => {
    const saved = loadRules();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- browser storage exists only on the client
    if (saved) setConfig(saved);
  }, []);
  const changeRules = (next: GpaConfig) => {
    setConfig(next);
    saveRules(next);
  };
  const query = useQuery({
    queryKey: ["grades", "mine"],
    queryFn: async () => unwrap(await api.GET("/api/v1/me/grades")).items,
  });
  const grades = query.data ?? [];
  return (
    <div className="flex flex-col gap-4">
      <ScreenState
        loading={query.isLoading}
        error={query.error}
        empty={false}
        emptyMessage=""
        errorMessage={t("error")}
        retryLabel={t("retry")}
        retry={() => void query.refetch()}
      />
      {query.isSuccess ? (
        <>
          <Summary grades={grades} config={config} />
          <CabinetCard />
          {grades.length > 0 ? <Courses grades={grades} config={config} /> : null}
          <Rules config={config} onChange={changeRules} />
          <Simulator grades={grades} config={config} />
        </>
      ) : null}
    </div>
  );
}

function Standing({ value }: { value: number }) {
  const t = useTranslations("gpa");
  return (
    <>
      {value >= TOP_TIER_FROM ? (
        <Tag tone="accent">{t("topTier", { n: TOP_TIER_FROM })}</Tag>
      ) : null}
      {value >= NO_LOAN_INTEREST_FROM ? (
        <Tag tone="success">{t("noLoanInterest", { n: NO_LOAN_INTEREST_FROM })}</Tag>
      ) : (
        <Tag>{t("belowLoanLine", { n: NO_LOAN_INTEREST_FROM })}</Tag>
      )}
    </>
  );
}

const TERMS = {
  fall: "terms.fall",
  spring: "terms.spring",
  summer: "terms.summer",
} as const;

function SemesterName({ semester }: { semester: SemesterResult["semester"] }) {
  const t = useTranslations("gpa");
  return <>{t("semesterName", { year: semester.year, term: t(TERMS[semester.term]) })}</>;
}

export function Summary({ grades, config }: { grades: Grade[]; config: GpaConfig }) {
  const t = useTranslations("gpa");
  const all = useMemo(() => semesterResults(grades), [grades]);
  const semesters = useMemo(() => {
    const keys = [...new Map(all.map((r) => [r.semesterKey, r.semester])).entries()];
    return keys.map(([key, semester]) => {
      const mine = all.filter((r) => r.semesterKey === key);
      return { key, semester, value: uomg(mine, config), credits: earnedCredits(mine, config) };
    });
  }, [all, config]);
  if (grades.length === 0) {
    return (
      <Panel>
        <PanelBody>
          <p>{t("empty")}</p>
        </PanelBody>
      </Panel>
    );
  }
  const total = uomg(all, config);
  return (
    <Panel aria-labelledby="gpa-total">
      <PanelHeader
        title={t("totalTitle")}
        titleId="gpa-total"
        description={t("totalDescription")}
      />
      <PanelBody className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-3xl font-semibold tabular" data-testid="gpa-total">
            {total.toFixed(config.roundDigits)}
          </p>
          <Tag>{t("letter", { letter: letterGrade(total) })}</Tag>
          <Standing value={total} />
        </div>
        <p className="text-sm text-muted tabular">
          {t("credits", { earned: earnedCredits(all, config), count: all.length })}
        </p>
        <Table>
          <TableCaption>{t("semestersTitle")}</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>{t("semester")}</TableHead>
              <TableHead numeric>{t("uomg")}</TableHead>
              <TableHead numeric>{t("earned")}</TableHead>
              <TableHead>{t("standing")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {semesters.map((semester) => (
              <TableRow key={semester.key}>
                <TableCell label={t("semester")}>
                  <SemesterName semester={semester.semester} />
                </TableCell>
                <TableCell label={t("uomg")} numeric>
                  {semester.value.toFixed(config.roundDigits)}
                </TableCell>
                <TableCell label={t("earned")} numeric>
                  {semester.credits}
                </TableCell>
                <TableCell label={t("standing")}>
                  <span className="flex flex-wrap gap-1">
                    <Standing value={semester.value} />
                  </span>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </PanelBody>
    </Panel>
  );
}

export function Courses({ grades, config }: { grades: Grade[]; config: GpaConfig }) {
  const t = useTranslations("gpa");
  const rows = useMemo(() => semesterResults(grades), [grades]);
  const newest = new Map<string, number>();
  for (const row of rows) {
    newest.set(row.courseId, Math.max(newest.get(row.courseId) ?? 0, row.attempt));
  }
  const counted = new Set(
    rows
      .filter(
        (row) => config.retakePolicy === "average" || newest.get(row.courseId) === row.attempt,
      )
      .map((row) => row.id),
  );
  return (
    <Panel aria-labelledby="gpa-courses">
      <PanelHeader title={t("coursesTitle")} titleId="gpa-courses" />
      <div className="px-4 pb-2">
        <Table>
          <TableCaption>{t("coursesTitle")}</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>{t("subject")}</TableHead>
              <TableHead>{t("semester")}</TableHead>
              <TableHead numeric>{t("creditsColumn")}</TableHead>
              <TableHead numeric>{t("score")}</TableHead>
              <TableHead>{t("status")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell label={t("subject")}>
                  {/* One block, so a long label in the stacked layout does not squeeze the name against the code. */}
                  <div className="min-w-0 max-md:text-right">
                    <span className="break-words">{row.name}</span>
                    <span className="block text-sm text-muted">{row.code}</span>
                  </div>
                </TableCell>
                <TableCell label={t("semester")}>
                  <SemesterName semester={row.semester} />
                </TableCell>
                <TableCell label={t("creditsColumn")} numeric>
                  {row.credits}
                </TableCell>
                <TableCell label={t("score")} numeric>
                  {row.score} · {letterGrade(row.score)}
                </TableCell>
                <TableCell label={t("status")}>
                  {!counted.has(row.id) ? (
                    <Tag>{t("replaced")}</Tag>
                  ) : row.score >= config.passThreshold ? (
                    <Tag tone="success">{t("passed")}</Tag>
                  ) : (
                    <Tag tone="danger">{t("failed")}</Tag>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Panel>
  );
}

function numberOr(value: string, fallback: number): number {
  const parsed = Number(value);
  return value.trim() !== "" && Number.isFinite(parsed) ? parsed : fallback;
}

export function Rules({
  config,
  onChange,
}: {
  config: GpaConfig;
  onChange: (next: GpaConfig) => void;
}) {
  const t = useTranslations("gpa");
  const set = (patch: Partial<GpaConfig>) => onChange({ ...config, ...patch });
  return (
    <Panel aria-labelledby="gpa-rules">
      <PanelHeader
        title={t("rulesTitle")}
        titleId="gpa-rules"
        description={t("rulesDescription")}
      />
      <PanelBody className="grid gap-4 sm:grid-cols-2">
        <Switch
          label={t("includeFailed")}
          description={t("includeFailedHelp")}
          checked={config.includeFailed}
          onCheckedChange={(includeFailed) => set({ includeFailed })}
        />
        <RadioGroup
          legend={t("retakePolicy")}
          value={config.retakePolicy}
          onValueChange={(value) => set({ retakePolicy: value as GpaConfig["retakePolicy"] })}
          options={[
            { value: "replace", label: t("retakeReplace"), description: t("retakeReplaceHelp") },
            { value: "average", label: t("retakeAverage"), description: t("retakeAverageHelp") },
          ]}
        />
        <Field label={t("roundDigits")}>
          <Select
            value={config.roundDigits}
            onChange={(event) => set({ roundDigits: Number(event.target.value) })}
          >
            {[0, 1, 2, 3].map((digits) => (
              <option key={digits} value={digits}>
                {digits}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("passThreshold")} helper={t("passThresholdHelp")}>
          <Input
            type="number"
            inputMode="numeric"
            min={0}
            max={100}
            value={config.passThreshold}
            onChange={(event) => set({ passThreshold: numberOr(event.target.value, 0) })}
          />
        </Field>
        <Field label={t("minExamScore")} helper={t("minExamScoreHelp")}>
          <Input
            type="number"
            inputMode="numeric"
            min={0}
            max={50}
            value={config.minExamScore}
            onChange={(event) => set({ minExamScore: numberOr(event.target.value, 0) })}
          />
        </Field>
        <div className="sm:col-span-2">
          <Button variant="tertiary" onClick={() => onChange(GPA_DEFAULTS)}>
            {t("resetRules")}
          </Button>
        </div>
      </PanelBody>
    </Panel>
  );
}

function formatDelta(value: number, digits: number): string {
  const text = Math.abs(value).toFixed(digits);
  if (Number(text) === 0) return text;
  return `${value > 0 ? "+" : "−"}${text}`;
}

export function Simulator({ grades, config }: { grades: Grade[]; config: GpaConfig }) {
  const t = useTranslations("gpa");
  const titleId = useId();
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [next, setNext] = useState(1);
  const outcome = simulate(grades, drafts, config);
  const update = (id: number, patch: Partial<Draft>) =>
    setDrafts((rows) => rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  return (
    <Panel aria-labelledby={titleId}>
      <PanelHeader
        title={t("simulatorTitle")}
        titleId={titleId}
        description={t("simulatorDescription")}
        action={
          <Button
            variant="secondary"
            onClick={() => {
              setDrafts((rows) => [
                ...rows,
                { id: next, credits: "5", semester: "35", exam: "35" },
              ]);
              setNext(next + 1);
            }}
          >
            <Plus aria-hidden className="size-4" />
            {t("addCourse")}
          </Button>
        }
      />
      <PanelBody className="flex flex-col gap-4">
        {drafts.length === 0 ? <p className="text-muted">{t("simulatorEmpty")}</p> : null}
        <ul className="flex flex-col gap-4">
          {drafts.map((draft, index) => (
            <li key={draft.id} className="grid grid-cols-2 items-end gap-3 sm:grid-cols-4">
              <Field label={t("draftCredits", { n: index + 1 })}>
                <Input
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={30}
                  value={draft.credits}
                  onChange={(event) => update(draft.id, { credits: event.target.value })}
                />
              </Field>
              <Field label={t("draftSemester", { n: index + 1 })}>
                <Input
                  type="number"
                  inputMode="numeric"
                  min={0}
                  max={50}
                  value={draft.semester}
                  onChange={(event) => update(draft.id, { semester: event.target.value })}
                />
              </Field>
              <Field
                label={t("draftExam", { n: index + 1 })}
                helper={t("draftExamHelp", { n: config.minExamScore })}
              >
                <Input
                  type="number"
                  inputMode="numeric"
                  min={0}
                  max={50}
                  value={draft.exam}
                  onChange={(event) => update(draft.id, { exam: event.target.value })}
                />
              </Field>
              <Button
                variant="tertiary"
                onClick={() => setDrafts((rows) => rows.filter((row) => row.id !== draft.id))}
              >
                <Trash2 aria-hidden className="size-4" />
                {t("removeCourse", { n: index + 1 })}
              </Button>
            </li>
          ))}
        </ul>
        {drafts.length > 0 ? (
          <div className="flex flex-col gap-1" aria-live="polite">
            <p className="tabular">
              {t("simulatedTotal")}:{" "}
              <strong data-testid="gpa-simulated">
                {outcome.after.toFixed(config.roundDigits)}
              </strong>
            </p>
            <p className="text-sm text-muted tabular" data-testid="gpa-delta">
              {t("delta", {
                value: formatDelta(outcome.after - outcome.before, config.roundDigits),
              })}
            </p>
          </div>
        ) : null}
      </PanelBody>
    </Panel>
  );
}
