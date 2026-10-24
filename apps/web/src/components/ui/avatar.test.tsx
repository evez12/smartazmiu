import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Avatar, initials } from "./avatar";

describe("initials", () => {
  it.each([
    ["Aysel Məmmədova", "AM"],
    ["ilkin əliyev", "İƏ"],
    ["ıspanaq", "I"],
    ["Nigar Gülnar İsmayılova", "Nİ"],
    ["  ", ""],
  ])("%s -> %s", (name, expected) => {
    expect(initials(name)).toBe(expected);
  });
});

describe("Avatar", () => {
  it("exposes the full name to assistive technology", () => {
    render(<Avatar name="Şəhla Ağayeva" />);
    expect(screen.getByText("Şəhla Ağayeva")).toHaveClass("sr-only");
  });
});
