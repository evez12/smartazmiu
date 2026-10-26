import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { ApiProvider } from "@/lib/api/provider";
import { renderWithIntl } from "@/test/render";

import { ChannelSidebar } from "./channel-sidebar";
import { Composer } from "./composer";
import type { Channel } from "./model";
import { PostingBanner } from "./posting";
import { ChatRuntimeProvider } from "./runtime";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));

const fetchMock = vi.fn<(request: Request) => Promise<Response>>();
beforeEach(() => vi.stubGlobal("fetch", fetchMock));
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function channel(overrides: Partial<Channel>): Channel {
  return {
    id: crypto.randomUUID(),
    type: "course_offering",
    name: "Statistika",
    context: "765a2 · 2026 Payız",
    peer: null,
    is_archived: false,
    is_readonly: false,
    notify_level: "all",
    muted_until: null,
    unread_count: 0,
    mention_count: 0,
    last_read_message_id: null,
    posting: { allowed: true, reason: null, until: null, retry_after_seconds: null },
    ...overrides,
  };
}

function renderInChat(ui: ReactElement) {
  return renderWithIntl(
    <ApiProvider csrfToken="csrf-0123">
      <ChatRuntimeProvider socketUrl="ws://localhost/ws" currentUserId="u-aysel">
        <ToastProvider>{ui}</ToastProvider>
      </ChatRuntimeProvider>
    </ApiProvider>,
  );
}

describe("Composer", () => {
  it("sends with Enter, keeps Shift+Enter for new lines and refuses empty text", async () => {
    const onSend = vi.fn();
    renderWithIntl(
      <Composer
        label="Mesaj"
        placeholder="Statistika kanalına yazın"
        disabled={false}
        onSend={onSend}
        onTyping={vi.fn()}
      />,
    );
    const field = screen.getByRole("combobox", { name: "Mesaj" });
    expect(field).toHaveAttribute("placeholder", "Statistika kanalına yazın");
    await userEvent.type(field, "   {Enter}");
    expect(onSend).not.toHaveBeenCalled();
    await userEvent.clear(field);
    await userEvent.type(field, "Birinci sətir{Shift>}{Enter}{/Shift}ikinci sətir{Enter}");
    expect(onSend).toHaveBeenCalledWith("Birinci sətir\nikinci sətir");
    expect(field).toHaveValue("");
  });

  it("counts characters near the limit and blocks sending beyond it", async () => {
    const onSend = vi.fn();
    renderWithIntl(
      <Composer
        label="Mesaj"
        placeholder="Statistika kanalına yazın"
        disabled={false}
        onSend={onSend}
        onTyping={vi.fn()}
      />,
    );
    const field = screen.getByRole("combobox", { name: "Mesaj" });
    await userEvent.click(field);
    await userEvent.paste("ə".repeat(3600));
    expect(screen.getByText("3600 / 4000 simvol")).toBeInTheDocument();
    await userEvent.paste("ə".repeat(401));
    expect(screen.getByText("Mesaj ən çox 4000 simvol ola bilər. Mətni qısaldın.")).toBeVisible();
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("button", { name: "Göndərin" })).toBeDisabled();
    await userEvent.keyboard("{Enter}");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("suggests channel members after @ and sends the pick as a mention token", async () => {
    const onSend = vi.fn();
    const ramin = { id: "r-1", display_name: "Ramin Əliyev", photo_url: null, badge: null };
    const rauf = { id: "r-2", display_name: "Rauf Səfərov", photo_url: null, badge: null };
    renderWithIntl(
      <Composer
        label="Mesaj"
        disabled={false}
        onSend={onSend}
        members={[ramin, rauf, { ...ramin, id: "me", display_name: "Aysel Məmmədova" }]}
        currentUserId="me"
      />,
    );
    const field = screen.getByRole("combobox", { name: "Mesaj" });
    await userEvent.type(field, "Salam @ra");
    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(2);
    expect(options[0]).toHaveTextContent("Ramin Əliyev");
    expect(options[1]).toHaveTextContent("Rauf Səfərov");
    expect(field).toHaveAttribute("aria-expanded", "true");
    await userEvent.keyboard("{ArrowDown}{Enter}");
    expect(field).toHaveValue("Salam @Rauf Səfərov ");
    await userEvent.type(field, "baxın{Enter}");
    expect(onSend).toHaveBeenCalledWith("Salam <@r-2> baxın");
  });

  it("is disabled when the channel does not accept posts", () => {
    renderWithIntl(<Composer label="Mesaj" disabled onSend={vi.fn()} onTyping={vi.fn()} />);
    expect(screen.getByRole("combobox", { name: "Mesaj" })).toBeDisabled();
  });
});

describe("PostingBanner", () => {
  it("names the specific reason, with its end time in Baku time (§13.2)", () => {
    const { rerender } = renderWithIntl(
      <PostingBanner
        posting={{
          allowed: false,
          reason: "chat.exam_mode",
          until: "2027-01-15T08:00:00Z",
          retry_after_seconds: null,
        }}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "İmtahan gedir. Kanal 15 Yanvar 2027, 12:00 qədər yalnız oxumaq üçündür.",
    );
    rerender(
      <PostingBanner
        posting={{
          allowed: false,
          reason: "chat.channel_archived",
          until: null,
          retry_after_seconds: null,
        }}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("kanal arxivdədir");
    rerender(
      <PostingBanner
        posting={{ allowed: true, reason: null, until: null, retry_after_seconds: null }}
      />,
    );
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

describe("ChannelSidebar", () => {
  it("groups channels with unread badges and presence for DMs, and shows the connection state", async () => {
    fetchMock.mockImplementation(async (request) => {
      const { pathname } = new URL(request.url);
      if (pathname === "/api/v1/chat/channels") {
        return json({
          channels: [
            channel({ name: "Statistika", unread_count: 3 }),
            channel({ name: "İKT-baza kompyuter bilikləri", is_archived: true }),
            channel({
              name: "Statistika",
              type: "subject_community",
              context: null,
              unread_count: 120,
            }),
            channel({ name: "765a2", type: "academic_group", context: null }),
            channel({
              name: "Ramin Əliyev",
              type: "dm",
              context: null,
              peer: { id: "u-ramin", display_name: "Ramin Əliyev", photo_url: null, badge: null },
            }),
          ],
          blocked_user_ids: [],
        });
      }
      // No socket: the ticket store is unavailable, so the client falls back to REST.
      if (pathname === "/api/v1/ws/ticket")
        return json({ error: { code: "chat.unavailable" } }, 503);
      return json({}, 404);
    });
    renderInChat(<ChannelSidebar />);
    const nav = await screen.findByRole("navigation", { name: "Kanallar" });
    await within(nav).findByRole("heading", { name: "Fənlər" });
    expect(
      within(nav)
        .getAllByRole("heading", { level: 2 })
        .map((h) => h.textContent),
    ).toEqual(["Fənlər", "Fənn icmaları", "Qrup", "Şəxsi"]);
    const course = within(nav).getAllByRole("link", { name: /Statistika/ })[0]!;
    expect(course).toHaveTextContent("765a2 · 2026 Payız");
    expect(course).toHaveTextContent("3 oxunmamış mesaj");
    expect(within(nav).getByText("99+")).toBeInTheDocument();
    expect(within(nav).getByText("Arxiv (1)")).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: /Ramin Əliyev/ })).toHaveTextContent("oflayn");
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        "Canlı bağlantı müvəqqəti əlçatan deyil",
      ),
    );
  });

  it("explains an empty list", async () => {
    fetchMock.mockImplementation(async (request) =>
      new URL(request.url).pathname === "/api/v1/chat/channels"
        ? json({ channels: [], blocked_user_ids: [] })
        : json({ error: { code: "chat.unavailable" } }, 503),
    );
    renderInChat(<ChannelSidebar />);
    expect(await screen.findByText(/Hələ heç bir kanalınız yoxdur/)).toBeInTheDocument();
  });
});
