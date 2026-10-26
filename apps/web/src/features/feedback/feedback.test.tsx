import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { ApiProvider } from "@/lib/api/provider";
import { renderWithIntl } from "@/test/render";

import { FeedbackDialog } from "./feedback-dialog";
import { FeedbackTable, type FeedbackItem } from "./feedback-table";

const router = { refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => "/schedule" }));

const fetchMock = vi.fn<(request: Request) => Promise<Response>>();
beforeEach(() => vi.stubGlobal("fetch", fetchMock));
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

function wrap(ui: React.ReactNode) {
  return renderWithIntl(
    <ApiProvider csrfToken="csrf-0123">
      <ToastProvider>{ui}</ToastProvider>
    </ApiProvider>,
  );
}

describe("FeedbackDialog", () => {
  it("asks for the text, then sends it with the current page and the contact choice", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ id: "f-1" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const onOpenChange = vi.fn();
    wrap(<FeedbackDialog open onOpenChange={onOpenChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Göndərin" }));
    expect(screen.getByText("Rəyinizi yazın.")).toBeVisible();
    expect(fetchMock).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("radio", { name: "Təklif" }));
    await userEvent.type(screen.getByRole("textbox"), "Cədvəldə otaq nömrəsini daha iri göstərin.");
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: "Göndərin" }));
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
    const request = fetchMock.mock.calls[0]![0];
    expect(new URL(request.url).pathname).toBe("/api/v1/feedback");
    expect(await request.json()).toEqual({
      category: "suggestion",
      message: "Cədvəldə otaq nömrəsini daha iri göstərin.",
      page: "/schedule",
      contact_ok: true,
    });
    expect(await screen.findByText("Rəyiniz göndərildi. Təşəkkür edirik.")).toBeVisible();
  });
});

describe("FeedbackTable", () => {
  const item: FeedbackItem = {
    id: "f-1",
    category: "problem",
    message: "Cədvəldə otaq göstərilmir.",
    page: "/schedule",
    contact_ok: true,
    status: "open",
    sender: {
      id: "u-aysel",
      display_name: "Aysel Məmmədova",
      email: "aysel.mammadova@smartazmiu.test",
    },
    handled_by: null,
    handled_at: null,
    created_at: "2026-10-26T08:00:00Z",
  };

  it("shows the feedback with its page and contact, and closes it", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ ...item, status: "closed" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    wrap(<FeedbackTable items={[item]} canHandle />);
    expect(screen.getByText("Səhifə: /schedule")).toBeVisible();
    expect(screen.getByText("aysel.mammadova@smartazmiu.test")).toBeVisible();
    expect(screen.getByText("Açıq")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Bağlayın" }));
    await waitFor(() => expect(router.refresh).toHaveBeenCalled());
    expect(await fetchMock.mock.calls[0]![0].json()).toEqual({ status: "closed" });
  });

  it("offers no actions without the handle permission", () => {
    wrap(
      <FeedbackTable
        items={[{ ...item, status: "closed", contact_ok: false }]}
        canHandle={false}
      />,
    );
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByText("Əlaqəyə razıdır")).toBeNull();
  });
});
