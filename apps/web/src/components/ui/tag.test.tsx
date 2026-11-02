import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Tag } from "./tag";

const LONG = "Müəllimlərin akademik məzuniyyətdə olan tələbələrlə əlaqə qaydaları";

describe("Tag", () => {
  it("keeps the whole text in the document and in the title when it is cut with an ellipsis", () => {
    render(<Tag>{LONG}</Tag>);
    const text = screen.getByText(LONG);
    expect(text).toHaveClass("truncate");
    // Not shortened in the markup: the accessible name is complete whatever the layout shows.
    expect(text.textContent).toBe(LONG);
    expect(text.closest("[title]")).toHaveAttribute("title", LONG);
    expect(screen.getByTitle(LONG)).toHaveClass("max-w-full");
  });

  it("is named by its full text for assistive technology", () => {
    render(
      <p>
        Status: <Tag tone="warning">{LONG}</Tag>
      </p>,
    );
    expect(screen.getByText(LONG)).toBeVisible();
    expect(screen.getByTitle(LONG).textContent).toBe(LONG);
  });
});
