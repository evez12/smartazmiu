import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { formatDayMonth, formatWeekdayDate } from "@/lib/format";
import { renderWithIntl } from "@/test/render";

import { ClassList } from "./class-list";
import {
  addDays,
  bakuToday,
  dayFromParam,
  mondayOf,
  visibleDays,
  type ClassItem,
  type ScheduleDay,
} from "./model";
import { TodayClasses, WeekView } from "./schedule-views";

const lecture: ClassItem = {
  id: "e1:2026-10-26",
  date: "2026-10-26",
  starts_at: "08:30",
  ends_at: "09:50",
  subject: { code: "IQT-2101", name: "Mikroiqtisadiyyat" },
  class_type: "lecture",
  room: {
    code: "1-301",
    name: "Mühazirə zalı",
    building: "Tədris korpusu 1",
    floor: "3-cü mərtəbə",
  },
  teachers: ["Şəhla Ağayeva"],
  groups: ["765a2"],
  status: "scheduled",
  original_date: "2026-10-26",
  original_starts_at: "08:30",
  moved_to: null,
  room_changed: false,
  teacher_changed: false,
  note: "",
};

function day(date: string, classes: ClassItem[] = []): ScheduleDay {
  return { date, parity: "upper", classes };
}

describe("calendar helpers", () => {
  it("uses the Baku date whatever the device's time zone", () => {
    // 21:30 UTC on Sunday is already Monday in Baku.
    expect(bakuToday(new Date("2026-10-25T21:30:00Z"))).toBe("2026-10-26");
    expect(bakuToday(new Date("2026-10-25T19:59:00Z"))).toBe("2026-10-25");
  });

  it("finds Mondays and adds days across months and years", () => {
    expect(mondayOf("2026-10-25")).toBe("2026-10-19");
    expect(mondayOf("2026-10-26")).toBe("2026-10-26");
    expect(mondayOf("2027-01-01")).toBe("2026-12-28");
    expect(addDays("2026-10-31", 1)).toBe("2026-11-01");
    expect(addDays("2027-01-01", -7)).toBe("2026-12-25");
  });

  it("falls back to today for malformed dates", () => {
    expect(dayFromParam("2026-11-09", "2026-10-25")).toBe("2026-11-09");
    expect(dayFromParam("09.11.2026", "2026-10-25")).toBe("2026-10-25");
    expect(dayFromParam("2026-13-45", "2026-10-25")).toBe("2026-10-25");
    expect(dayFromParam(undefined, "2026-10-25")).toBe("2026-10-25");
  });

  it("formats calendar dates in Azerbaijani", () => {
    expect(formatDayMonth("2026-10-26")).toBe("26 Oktyabr");
    expect(formatWeekdayDate("2026-10-26")).toBe("Bazar ertəsi, 26 Oktyabr");
    expect(formatWeekdayDate("2026-10-27")).toBe("Çərşənbə axşamı, 27 Oktyabr");
  });

  it("shows the weekend only when it has classes", () => {
    const week = ["26", "27", "28", "29", "30", "31"].map((d) => day(`2026-10-${d}`));
    const weekend = [...week, day("2026-11-01")];
    expect(visibleDays(weekend)).toHaveLength(5);
    weekend[5] = day("2026-10-31", [lecture]);
    expect(visibleDays(weekend).map((d) => d.date)).toContain("2026-10-31");
  });
});

describe("ClassList", () => {
  it("links the room to the map and lists teachers and groups", () => {
    renderWithIntl(<ClassList classes={[lecture]} />);
    const room = screen.getByRole("link", { name: "1-301 otağını xəritədə göstərin" });
    expect(room).toHaveAttribute("href", "/map?room=1-301");
    expect(screen.getByText("08:30–09:50")).toBeInTheDocument();
    expect(screen.getByText("Mühazirə")).toBeInTheDocument();
    expect(screen.getByText("Şəhla Ağayeva")).toBeInTheDocument();
    expect(screen.queryByText("Dəyişiklik")).not.toBeInTheDocument();
  });

  it("marks changes with text, not colour alone", () => {
    renderWithIntl(
      <ClassList
        classes={[
          { ...lecture, status: "cancelled", note: "Dövlət Bayrağı Günü" },
          {
            ...lecture,
            id: "e2:2026-10-28",
            status: "moved_away",
            moved_to: { date: "2026-10-30", starts_at: "10:05", ends_at: "11:25" },
          },
          { ...lecture, id: "e3:2026-10-29", status: "changed", room_changed: true, room: null },
        ]}
      />,
    );
    const [cancelled, moved, changed] = screen.getAllByRole("listitem");
    expect(within(cancelled!).getByText("Ləğv olunub")).toBeInTheDocument();
    expect(within(cancelled!).getByText("Dövlət Bayrağı Günü")).toBeInTheDocument();
    expect(within(moved!).getByText("Köçürülüb")).toBeInTheDocument();
    expect(
      within(moved!).getByText("Dərs Cümə, 30 Oktyabr, saat 10:05 vaxtına köçürülüb."),
    ).toBeInTheDocument();
    expect(within(changed!).getByText("Dəyişiklik")).toBeInTheDocument();
    expect(within(changed!).getByText("Otaq dəyişib.")).toBeInTheDocument();
    expect(within(changed!).getByText("Otaq göstərilməyib")).toBeInTheDocument();
  });
});

describe("schedule views", () => {
  it("explains an empty week and offers the next one", () => {
    renderWithIntl(
      <WeekView
        schedule={{
          start: "2026-12-28",
          end: "2027-01-03",
          today: "2026-12-29",
          days: Array.from({ length: 7 }, (_, i) => ({
            ...day(addDays("2026-12-28", i)),
            parity: "lower" as const,
          })),
        }}
      />,
    );
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "28 Dekabr – 3 Yanvar · Alt həftə",
    );
    expect(screen.getByText("Bu həftə dərsiniz yoxdur.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Növbəti həftəyə baxın" })).toHaveAttribute(
      "href",
      "/schedule?view=week&date=2027-01-04",
    );
  });

  it("shows today's classes on the dashboard", () => {
    renderWithIntl(
      <TodayClasses
        schedule={{
          start: "2026-10-26",
          end: "2026-10-26",
          today: "2026-10-26",
          days: [day("2026-10-26", [lecture])],
        }}
      />,
    );
    expect(screen.getByRole("heading", { name: "Bugünkü dərslər" })).toBeInTheDocument();
    expect(screen.getByText("Bazar ertəsi, 26 Oktyabr · Üst həftə")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Həftəlik cədvəl" })).toHaveAttribute(
      "href",
      "/schedule?view=week&date=2026-10-26",
    );
  });

  it("explains a day without classes outside the semester", () => {
    renderWithIntl(
      <TodayClasses
        schedule={{
          start: "2026-07-06",
          end: "2026-07-06",
          today: "2026-07-06",
          days: [{ date: "2026-07-06", parity: null, classes: [] }],
        }}
      />,
    );
    expect(screen.getByText("Bazar ertəsi, 6 İyul · Semestrdən kənar")).toBeInTheDocument();
    expect(screen.getByText("Bu gün dərsiniz yoxdur.")).toBeInTheDocument();
  });
});
