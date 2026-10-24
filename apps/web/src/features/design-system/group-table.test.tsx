import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { renderWithIntl } from "@/test/render";

import { GroupTable } from "./group-table";

function firstColumn() {
  return screen
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("cell")[0]?.textContent);
}

describe("GroupTable", () => {
  it("sorts by group code and toggles direction", async () => {
    renderWithIntl(<GroupTable />);
    const groupHeader = screen.getByRole("columnheader", { name: /Qrup/ });
    expect(groupHeader).toHaveAttribute("aria-sort", "ascending");
    expect(firstColumn()).toEqual(["713a2", "742a1", "765a2", "781b3"]);

    await userEvent.click(screen.getByRole("button", { name: "Qrup üzrə sıralayın" }));
    expect(groupHeader).toHaveAttribute("aria-sort", "descending");
    expect(firstColumn()).toEqual(["781b3", "765a2", "742a1", "713a2"]);
  });

  it("sorts numerically by student count", async () => {
    renderWithIntl(<GroupTable />);
    await userEvent.click(screen.getByRole("button", { name: "Tələbə sayı üzrə sıralayın" }));
    expect(screen.getByRole("columnheader", { name: /Tələbə sayı/ })).toHaveAttribute(
      "aria-sort",
      "ascending",
    );
    expect(firstColumn()).toEqual(["713a2", "742a1", "765a2", "781b3"]);
  });

  it("labels every cell for the stacked mobile layout", () => {
    renderWithIntl(<GroupTable />);
    const cells = screen.getAllByRole("cell");
    expect(cells.every((cell) => cell.dataset.label)).toBe(true);
  });
});
