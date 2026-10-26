import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { touchTarget } from "./touch-target";
import { TextLink } from "./text-link";

describe("TextLink", () => {
  it("gets the 44 px touch area when it stands on its own", () => {
    render(<TextLink href="/chat">Çata keçin</TextLink>);
    expect(screen.getByRole("link", { name: "Çata keçin" }).className).toContain(
      "after:min-h-[44px]",
    );
  });

  it("leaves links inside a sentence alone, so they do not cover the words around them", () => {
    render(
      <TextLink inline href="/privacy">
        Bildirişi oxuyun
      </TextLink>,
    );
    const link = screen.getByRole("link", { name: "Bildirişi oxuyun" });
    expect(link.className).not.toContain("after:min-h-[44px]");
  });

  it("sizes the touch area in pixels, independent of the root font size", () => {
    expect(touchTarget).toContain("after:min-h-[44px]");
    expect(touchTarget).toContain("after:min-w-[44px]");
    expect(touchTarget).toContain("pointer-fine:after:hidden");
  });
});
