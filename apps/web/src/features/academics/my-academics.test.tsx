import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithIntl } from "@/test/render";

import { MyAcademics } from "./my-academics";

const micro = {
  offering_id: "o1",
  offering_code: "765a2",
  subject: { code: "IQT-2101", name: "Mikroiqtisadiyyat", credits: 10 },
  semester: { year: 2026, term: "fall" as const },
  groups: ["765a2"],
  teachers: ["Şəhla Ağayeva", "Fərid İsmayılov"],
};

describe("MyAcademics", () => {
  it("shows the student's group and current subjects", () => {
    renderWithIntl(
      <MyAcademics
        data={{
          group: {
            code: "765a2",
            admission_year: 2025,
            language: "az",
            specialty: { code: "6004004", name: "İqtisadiyyat" },
            faculty: { code: "TIQ", name: "Tikinti iqtisadiyyatı fakültəsi" },
          },
          courses: [micro, { ...micro, offering_id: "o2", teachers: [] }],
          teaching: [],
        }}
      />,
    );
    expect(screen.getByRole("heading", { name: "Qrupunuz" })).toBeInTheDocument();
    expect(screen.getByText("İqtisadiyyat · 6004004")).toBeInTheDocument();
    expect(screen.getByText("Azərbaycan dili")).toBeInTheDocument();
    expect(screen.getByText("2026 Payız semestrində keçdiyiniz fənlər.")).toBeInTheDocument();
    const rows = within(screen.getByRole("table", { name: "Fənləriniz" })).getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(rows[1]).toHaveTextContent("Şəhla Ağayeva, Fərid İsmayılov");
    expect(rows[2]).toHaveTextContent("Təyin edilməyib");
    expect(screen.queryByText("Dərs dediyiniz fənlər")).not.toBeInTheDocument();
  });

  it("explains a group without subjects yet", () => {
    renderWithIntl(
      <MyAcademics
        data={{
          group: {
            code: "766a1",
            admission_year: 2026,
            language: "ru",
            specialty: { code: "6004004", name: "İqtisadiyyat" },
            faculty: { code: "TIQ", name: "Tikinti iqtisadiyyatı fakültəsi" },
          },
          courses: [],
          teaching: [],
        }}
      />,
    );
    expect(
      screen.getByText("Bu semestr üçün fənləriniz hələ əlavə olunmayıb."),
    ).toBeInTheDocument();
    expect(screen.getByText("Rus dili")).toBeInTheDocument();
  });

  it("shows a teacher's current teaching", () => {
    renderWithIntl(
      <MyAcademics
        data={{ group: null, courses: [], teaching: [{ ...micro, student_count: 22 }] }}
      />,
    );
    const table = screen.getByRole("table", { name: "Dərs dediyiniz fənlər" });
    expect(within(table).getAllByRole("row")[1]).toHaveTextContent("2026 Payız");
    expect(within(table).getAllByRole("row")[1]).toHaveTextContent("22");
    expect(screen.queryByRole("heading", { name: "Qrupunuz" })).not.toBeInTheDocument();
  });

  it("falls back to the explanatory empty state without academic data", () => {
    renderWithIntl(<MyAcademics data={{ group: null, courses: [], teaching: [] }} />);
    expect(
      screen.getByText("Qrupunuz, fənləriniz və dərs cədvəliniz hələ idxal olunmayıb."),
    ).toBeInTheDocument();
  });
});
