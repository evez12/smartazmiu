import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithIntl } from "@/test/render";

import { FloorPlan, RoomFacts, type FloorPlanData } from "./floor-plan";

const plan: FloorPlanData = {
  building: { code: "1", name: "Tədris korpusu 1" },
  level: 3,
  name: "3-cü mərtəbə",
  width: 600,
  height: 200,
  rooms: [
    {
      code: "1-301",
      name: "Mühazirə zalı",
      type: "lecture_hall",
      capacity: 90,
      x: 0,
      y: 0,
      width: 140,
      height: 80,
    },
    {
      code: "1-305",
      name: "",
      type: "classroom",
      capacity: 30,
      x: 410,
      y: 0,
      width: 90,
      height: 80,
    },
    {
      code: "1-306",
      name: "Pilləkən",
      type: "service",
      capacity: null,
      x: 500,
      y: 0,
      width: 100,
      height: 80,
    },
  ],
};

describe("FloorPlan", () => {
  it("draws every room as a keyboard-reachable link and marks the selected one", () => {
    renderWithIntl(<FloorPlan plan={plan} selected="1-305" />);

    expect(
      screen.getByRole("group", { name: "Tədris korpusu 1, 3-cü mərtəbə: plan" }),
    ).toBeInTheDocument();
    const selected = screen.getByRole("link", { name: "1-305, Auditoriya" });
    expect(selected).toHaveAttribute("href", "/map?room=1-305");
    expect(selected).toHaveAttribute("aria-current", "location");
    const other = screen.getByRole("link", { name: "1-301, Mühazirə zalı" });
    expect(other).not.toHaveAttribute("aria-current");
    expect(screen.getAllByRole("link")).toHaveLength(3);

    const rect = selected.querySelector("rect")!;
    expect(rect.getAttribute("x")).toBe("410");
    expect(rect.getAttribute("width")).toBe("90");
    expect(rect.getAttribute("class")).toContain("fill-primary");
  });

  it("lists the facts of a room", () => {
    renderWithIntl(
      <RoomFacts
        room={{
          code: "2-204",
          name: "Statistika laboratoriyası",
          type: "laboratory",
          capacity: 24,
          building: { code: "2", name: "Tədris korpusu 2" },
          floor: { level: 2, name: "2-ci mərtəbə" },
        }}
        address="Ayna Sultanova küçəsi 11, Bakı"
      />,
    );
    expect(screen.getByText("Statistika laboratoriyası")).toBeInTheDocument();
    expect(screen.getByText("Laboratoriya")).toBeInTheDocument();
    expect(screen.getByText("24")).toBeInTheDocument();
    expect(screen.getByText("2-ci mərtəbə")).toBeInTheDocument();
  });
});
