import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { ApiProvider } from "@/lib/api/provider";
import { renderWithIntl } from "@/test/render";

import { ReportDialog } from "./report-dialog";
import { ReportTable, type ReportItem } from "./report-table";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }) }));

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

const RAMIN = { id: "u-ramin", display_name: "Ramin Əliyev", photo_url: null, badge: null };

function item(overrides: Partial<ReportItem>): ReportItem {
  return {
    id: crypto.randomUUID(),
    target_type: "message",
    reason: "spam",
    note: "",
    status: "open",
    created_at: "2026-10-26T08:00:00Z",
    reporter: { id: "u-aysel", display_name: "Aysel Məmmədova", photo_url: null, badge: null },
    reported_user: RAMIN,
    message: {
      id: "1",
      channel_id: "c-1",
      channel_name: "Statistika",
      author: RAMIN,
      body: "Reklam",
      deleted: false,
      created_at: "2026-10-26T07:55:00Z",
    },
    handled_by: null,
    handled_at: null,
    reporters: 1,
    ...overrides,
  };
}

describe("ReportDialog", () => {
  it("asks for a reason, then sends the report once", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ id: "r-1", status: "open", duplicate: false }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const onOpenChange = vi.fn();
    wrap(<ReportDialog open onOpenChange={onOpenChange} targetType="message" targetId="42" />);
    await userEvent.click(screen.getByRole("button", { name: "Şikayət göndərin" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Səbəbi seçin.");
    expect(fetchMock).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("radio", { name: /İmtahan suallarının yayılması/ }));
    await userEvent.type(screen.getByRole("textbox"), "Cari semestrin sualları");
    await userEvent.click(screen.getByRole("button", { name: "Şikayət göndərin" }));
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
    const request = fetchMock.mock.calls[0]![0];
    expect(new URL(request.url).pathname).toBe("/api/v1/reports");
    expect(await request.json()).toEqual({
      target_type: "message",
      target_id: "42",
      reason: "exam_leak",
      note: "Cari semestrin sualları",
    });
  });
});

describe("ReportTable", () => {
  it("shows reported text as plain text, the status in words and actions only to handlers", () => {
    wrap(
      <ReportTable
        caption="Şikayətlər"
        canHandle={false}
        items={[
          item({
            message: { ...item({}).message!, body: "<script>alert(1)</script>", deleted: true },
          }),
          item({ target_type: "user", message: null, status: "dismissed", reporters: 3 }),
        ]}
      />,
    );
    expect(screen.getByText("<script>alert(1)</script>")).toBeVisible();
    expect(document.querySelector("script")).toBeNull();
    expect(screen.getByText("Müəllif mesajı silib")).toBeVisible();
    expect(screen.getAllByText("Rədd edilib").length).toBeGreaterThan(0);
    expect(screen.getByText("3 şikayətçi")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Rədd edin" })).toBeNull();
  });
});
