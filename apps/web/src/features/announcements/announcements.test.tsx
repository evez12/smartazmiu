import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { ApiProvider } from "@/lib/api/provider";
import { bakuInputToIso, isoToBakuInput } from "@/lib/format";
import { renderWithIntl } from "@/test/render";

import { AnnouncementEditor } from "./announcement-editor";
import { AnnouncementList } from "./announcement-list";
import type { Announcement } from "./model";

const push = vi.fn();
const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh }) }));

const fetchMock = vi.fn<(request: Request) => Promise<Response>>();

beforeEach(() => vi.stubGlobal("fetch", fetchMock));
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  push.mockReset();
  refresh.mockReset();
});

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderInApp(ui: ReactElement) {
  return renderWithIntl(
    <ApiProvider csrfToken="csrf-0123">
      <ToastProvider>{ui}</ToastProvider>
    </ApiProvider>,
  );
}

const announcement: Announcement = {
  id: "01a174b4-3a29-7eca-8038-126c35db06fe",
  title: "Qış imtahan sessiyasının cədvəli dərc olundu",
  body: "Cədvəl dekanlığın lövhəsindədir.\nSualınız varsa, kuratora yazın.",
  status: "published",
  audience: { type: "group", target_id: "01a1", label: "765a2", detail: "İqtisadiyyat" },
  published_at: "2026-12-01T05:00:00Z",
  expires_at: null,
  version: 1,
};

describe("Baku date-time inputs", () => {
  it("reads and writes datetime-local values in Baku time", () => {
    expect(bakuInputToIso("2026-12-01T09:00")).toBe("2026-12-01T09:00:00+04:00");
    expect(isoToBakuInput("2026-12-01T05:00:00Z")).toBe("2026-12-01T09:00");
    // 21:30 UTC is already the next day in Baku.
    expect(isoToBakuInput("2026-12-31T21:30:00Z")).toBe("2027-01-01T01:30");
  });
});

describe("AnnouncementList", () => {
  it("shows title, audience and the Baku publication time", () => {
    renderWithIntl(<AnnouncementList items={[announcement]} />);
    expect(screen.getByRole("link", { name: announcement.title })).toHaveAttribute(
      "href",
      `/announcements/${announcement.id}`,
    );
    expect(screen.getByText(/Qrup · 765a2/)).toBeInTheDocument();
    expect(screen.getByText("1 Dekabr 2026, 09:00")).toBeInTheDocument();
  });
});

describe("AnnouncementEditor", () => {
  it("explains what is missing before publishing", async () => {
    renderInApp(<AnnouncementEditor />);
    await userEvent.selectOptions(screen.getByLabelText(/Kimə/), "group");
    fetchMock.mockResolvedValue(json({ items: [] }));
    await userEvent.click(screen.getByRole("button", { name: "Dərc edin" }));
    expect(screen.getByText("Başlıq yazın.")).toBeInTheDocument();
    expect(screen.getByText("Mətn yazın.")).toBeInTheDocument();
    expect(await screen.findByText("Auditoriyanı seçin.")).toBeInTheDocument();
    expect(fetchMock.mock.calls.every(([request]) => request.method === "GET")).toBe(true);
  });

  it("publishes to a chosen group with an idempotency key", async () => {
    fetchMock.mockImplementation(async (request) => {
      if (request.method === "GET") {
        return json({
          items: [
            { id: "g-765a1", label: "765a1", detail: "İqtisadiyyat" },
            { id: "g-765a2", label: "765a2", detail: "İqtisadiyyat" },
          ],
        });
      }
      return json(announcement, 201);
    });
    renderInApp(<AnnouncementEditor />);
    await userEvent.type(screen.getByRole("textbox", { name: /Başlıq/ }), "Qış sessiyası");
    await userEvent.type(screen.getByRole("textbox", { name: /Mətn/ }), "Cədvəl hazırdır.");
    await userEvent.selectOptions(screen.getByLabelText(/Kimə/), "group");
    await userEvent.type(screen.getByRole("searchbox", { name: "Axtarış" }), "765");
    await userEvent.click(await screen.findByRole("radio", { name: "765a2" }));
    await userEvent.type(screen.getByLabelText("Bitmə vaxtı"), "2026-12-20T18:00");
    await userEvent.click(screen.getByRole("button", { name: "Dərc edin" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith(`/announcements/${announcement.id}`));
    const searches = fetchMock.mock.calls.map(([request]) => new URL(request.url));
    expect(searches.some((url) => url.searchParams.get("q") === "765")).toBe(true);
    const post = fetchMock.mock.calls.find(([request]) => request.method === "POST")![0];
    expect(post.headers.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
    expect(await post.json()).toEqual({
      title: "Qış sessiyası",
      body: "Cədvəl hazırdır.",
      expires_at: "2026-12-20T18:00:00+04:00",
      audience: { type: "group", target_id: "g-765a2" },
    });
  });

  it("corrects text without offering to change the audience, and explains a conflict", async () => {
    fetchMock.mockResolvedValue(
      json(
        { error: { code: "announcements.version_conflict", message: "Elan dəyişdirilib." } },
        409,
      ),
    );
    renderInApp(<AnnouncementEditor announcement={announcement} />);
    expect(screen.queryByLabelText(/Kimə/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Yadda saxlayın" }));
    expect(await screen.findByText("Elan dəyişdirilib.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Səhifəni yeniləyin" })).toBeInTheDocument();
    const request = fetchMock.mock.calls[0]![0];
    expect(request.method).toBe("PATCH");
    expect(await request.json()).toEqual({
      version: 1,
      title: announcement.title,
      body: announcement.body,
      expires_at: null,
    });
  });
});
