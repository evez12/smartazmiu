import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { ApiProvider } from "@/lib/api/provider";
import { renderWithIntl } from "@/test/render";

import { AcknowledgeButton } from "./acknowledge-button";
import { ConsentHistory, NoticePrompt, type MyConsents } from "./privacy-parts";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh }) }));

const fetchMock = vi.fn<(request: Request) => Promise<Response>>();
beforeEach(() => vi.stubGlobal("fetch", fetchMock));
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  refresh.mockReset();
});

const pending: MyConsents = {
  notice_version: "2026-10",
  notice_acknowledged_at: null,
  history: [],
};

describe("NoticePrompt", () => {
  it("asks to read the notice until it is acknowledged", () => {
    const { rerender } = renderWithIntl(<NoticePrompt consents={pending} />);
    expect(screen.getByRole("status")).toHaveTextContent("Məxfilik bildirişi ilə tanış olun");
    expect(screen.getByRole("link", { name: "Bildirişi oxuyun" })).toHaveAttribute(
      "href",
      "/privacy",
    );

    rerender(
      <NoticePrompt consents={{ ...pending, notice_acknowledged_at: "2026-10-25T08:00:00Z" }} />,
    );
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

describe("ConsentHistory", () => {
  it("shows purposes and decisions in Azerbaijani", () => {
    renderWithIntl(
      <ConsentHistory
        consents={{
          ...pending,
          history: [
            {
              purpose: "contact_sharing",
              granted: false,
              policy_version: null,
              recorded_at: "2026-10-25T09:00:00Z",
            },
            {
              purpose: "contact_sharing",
              granted: true,
              policy_version: null,
              recorded_at: "2026-10-24T21:30:00Z",
            },
          ],
        }}
      />,
    );
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("25 Oktyabr 2026, 13:00");
    expect(rows[1]).toHaveTextContent("E-poçtun digər istifadəçilərə göstərilməsi");
    expect(rows[1]).toHaveTextContent("Geri alınıb");
    expect(rows[2]).toHaveTextContent("25 Oktyabr 2026, 01:30");
    expect(rows[2]).toHaveTextContent("Razılıq verilib");
  });

  it("explains an empty history", () => {
    renderWithIntl(<ConsentHistory consents={pending} />);
    expect(screen.getByText("Hələ heç bir razılıq qeydə alınmayıb.")).toBeInTheDocument();
  });
});

describe("AcknowledgeButton", () => {
  it("records the acknowledgement of the shown version", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ ...pending, notice_acknowledged_at: "2026-10-25T09:00:00Z" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    renderWithIntl(
      <ApiProvider csrfToken="csrf-0123">
        <ToastProvider>
          <AcknowledgeButton version="2026-10" />
        </ToastProvider>
      </ApiProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Tanış oldum" }));

    await waitFor(() => expect(refresh).toHaveBeenCalled());
    const request = fetchMock.mock.calls[0]![0];
    expect(new URL(request.url).pathname).toBe("/api/v1/me/consents/privacy-notice");
    expect(request.headers.get("x-csrf-token")).toBe("csrf-0123");
    expect(await request.json()).toEqual({ version: "2026-10" });
  });
});
