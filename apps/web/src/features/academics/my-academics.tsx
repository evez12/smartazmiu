import { GraduationCap } from "lucide-react";
import { useTranslations } from "next-intl";

import { EmptyState } from "@/components/ui/empty-state";
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
import type { components } from "@/lib/api/schema";

type MyAcademicsResponse = components["schemas"]["MyAcademicsResponse"];
type Course = components["schemas"]["CourseOut"];
type TeachingCourse = components["schemas"]["TeachingCourseOut"];
type Semester = components["schemas"]["SemesterRef"];

function useSemesterLabel() {
  const t = useTranslations("academics");
  return (semester: Semester) =>
    t("semesterLabel", { year: semester.year, term: t(`terms.${semester.term}`) });
}

/** The dashboard's academic section: own group, current subjects and, for teachers, current teaching. */
export function MyAcademics({ data }: { data: MyAcademicsResponse }) {
  if (!data.group && data.courses.length === 0 && data.teaching.length === 0) {
    return <NoAcademicData />;
  }
  return (
    <div className="flex flex-col gap-6">
      {data.group ? <GroupPanel group={data.group} /> : null}
      {data.group || data.courses.length > 0 ? <CoursesPanel courses={data.courses} /> : null}
      {data.teaching.length > 0 ? <TeachingPanel courses={data.teaching} /> : null}
    </div>
  );
}

/** "User with no enrollments": an explanation, not an error (§13.1). */
function NoAcademicData() {
  const t = useTranslations("dashboard");
  return (
    <Panel>
      <PanelHeader title={t("academicDataTitle")} />
      <PanelBody>
        <EmptyState
          className="py-2"
          icon={GraduationCap}
          message={t("noAcademicData")}
          action={<p className="max-w-[75ch] text-sm text-muted">{t("noAcademicDataHint")}</p>}
        />
      </PanelBody>
    </Panel>
  );
}

type GroupPlacement = NonNullable<MyAcademicsResponse["group"]>;

/** Group, specialty, faculty, admission year and language; shown on the dashboard and the profile. */
export function GroupFacts({ group }: { group: GroupPlacement }) {
  const t = useTranslations("academics");
  const facts = [
    { label: t("group"), value: group.code },
    { label: t("specialty"), value: `${group.specialty.name} · ${group.specialty.code}` },
    { label: t("faculty"), value: group.faculty.name },
    { label: t("admissionYear"), value: String(group.admission_year) },
    { label: t("language"), value: t(`languages.${group.language}`) },
  ];
  return (
    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
      {facts.map((fact) => (
        <div key={fact.label} className="flex flex-col">
          <dt className="text-sm text-muted">{fact.label}</dt>
          <dd className="text-text tabular">{fact.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function GroupPanel({ group }: { group: GroupPlacement }) {
  const t = useTranslations("academics");
  return (
    <Panel>
      <PanelHeader title={t("groupTitle")} />
      <PanelBody>
        <GroupFacts group={group} />
      </PanelBody>
    </Panel>
  );
}

function SubjectCell({ course, label }: { course: Course; label: string }) {
  return (
    <TableCell label={label}>
      <span className="flex flex-col max-md:items-end max-md:text-right">
        <span>{course.subject.name}</span>
        <span className="text-sm text-muted">{course.subject.code}</span>
      </span>
    </TableCell>
  );
}

function CoursesPanel({ courses }: { courses: Course[] }) {
  const t = useTranslations("academics");
  const semesterLabel = useSemesterLabel();
  const semesters = [...new Set(courses.map((course) => semesterLabel(course.semester)))];
  return (
    <Panel>
      <PanelHeader
        title={t("coursesTitle")}
        description={
          semesters.length ? t("coursesDescription", { semester: semesters.join(", ") }) : undefined
        }
      />
      {courses.length === 0 ? (
        <PanelBody>
          <EmptyState className="py-0" message={t("noCourses")} />
        </PanelBody>
      ) : (
        <div className="px-4 pb-2">
          <Table>
            <TableCaption>{t("coursesTitle")}</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>{t("subject")}</TableHead>
                <TableHead numeric>{t("credits")}</TableHead>
                <TableHead>{t("teachers")}</TableHead>
                <TableHead>{t("groups")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {courses.map((course) => (
                <TableRow key={course.offering_id}>
                  <SubjectCell course={course} label={t("subject")} />
                  <TableCell label={t("credits")} numeric>
                    {course.subject.credits}
                  </TableCell>
                  <TableCell label={t("teachers")}>
                    {course.teachers.length ? course.teachers.join(", ") : t("noTeacher")}
                  </TableCell>
                  <TableCell label={t("groups")}>{course.groups.join(", ")}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </Panel>
  );
}

function TeachingPanel({ courses }: { courses: TeachingCourse[] }) {
  const t = useTranslations("academics");
  const semesterLabel = useSemesterLabel();
  return (
    <Panel>
      <PanelHeader title={t("teachingTitle")} description={t("teachingDescription")} />
      <div className="px-4 pb-2">
        <Table>
          <TableCaption>{t("teachingTitle")}</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>{t("subject")}</TableHead>
              <TableHead>{t("semester")}</TableHead>
              <TableHead>{t("groups")}</TableHead>
              <TableHead numeric>{t("students")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {courses.map((course) => (
              <TableRow key={course.offering_id}>
                <SubjectCell course={course} label={t("subject")} />
                <TableCell label={t("semester")}>{semesterLabel(course.semester)}</TableCell>
                <TableCell label={t("groups")}>{course.groups.join(", ")}</TableCell>
                <TableCell label={t("students")} numeric>
                  {course.student_count}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Panel>
  );
}
