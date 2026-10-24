import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithIntl } from "@/test/render";

import { CountBadge } from "./count-badge";

describe("CountBadge", () => {
  it("caps the visible number but announces the real count", () => {
    renderWithIntl(<CountBadge count={128} />);
    expect(screen.getByText("99+")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByText("128 oxunmamış mesaj")).toHaveClass("sr-only");
  });

  it("distinguishes mentions by text, not only colour", () => {
    renderWithIntl(<CountBadge count={2} kind="mention" />);
    expect(screen.getByText("2 qeyd olunma")).toBeInTheDocument();
  });

  it("renders nothing for zero", () => {
    const { container } = renderWithIntl(<CountBadge count={0} />);
    expect(container).toBeEmptyDOMElement();
  });
});
