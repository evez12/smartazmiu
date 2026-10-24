import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./button";

describe("Button", () => {
  it("defaults to a non-submitting secondary button", () => {
    render(<Button>Ləğv edin</Button>);
    const button = screen.getByRole("button", { name: "Ləğv edin" });
    expect(button).toHaveAttribute("type", "button");
    expect(button.className).toContain("border-border-control");
  });

  it("blocks repeat clicks and announces progress while loading", async () => {
    const onClick = vi.fn();
    render(
      <Button variant="primary" loading onClick={onClick}>
        Göndərilir
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Göndərilir" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("renders the child element when asChild is set", () => {
    render(
      <Button asChild variant="tertiary">
        <a href="/design-system">Ətraflı baxın</a>
      </Button>,
    );
    expect(screen.getByRole("link", { name: "Ətraflı baxın" })).toHaveClass("text-primary");
  });
});
