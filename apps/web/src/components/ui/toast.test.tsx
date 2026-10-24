import { act, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithIntl } from "@/test/render";

import { TOAST_DURATION_MS, ToastProvider, useToast } from "./toast";

function Trigger() {
  const toast = useToast();
  return (
    <button type="button" onClick={() => toast({ title: "Dəyişikliklər yadda saxlanıldı" })}>
      show
    </button>
  );
}

describe("toast", () => {
  it("never stays longer than four seconds", () => {
    expect(TOAST_DURATION_MS).toBeLessThanOrEqual(4000);
  });

  it("shows the confirmation in a live region", async () => {
    renderWithIntl(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    );
    await act(async () => screen.getByRole("button", { name: "show" }).click());
    expect((await screen.findAllByText("Dəyişikliklər yadda saxlanıldı")).length).toBeGreaterThan(
      0,
    );
  });

  it("requires the provider", () => {
    expect(() => renderWithIntl(<Trigger />)).toThrow(/ToastProvider/);
  });
});
