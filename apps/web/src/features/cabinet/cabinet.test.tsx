import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { ApiProvider } from "@/lib/api/provider";
import { fetchMock, json, serve } from "@/test/api";
import { renderWithIntl } from "@/test/render";

import { CabinetCard } from "./cabinet-card";
import { SyncAdmin } from "./sync-admin";
import { TranscriptPage } from "./transcript-page";

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

const SYNCED = "2026-11-03T22:40:00Z";

function course(code: string, name: string, score: number, differs = false) {
  return {
    subject_code: code,
    subject_name: name,
    credits: 5,
    score,
    passed: score >= 51,
    differs,
  };
}

function transcript(overrides: Record<string, unknown> = {}) {
  return {
    source: { state: "ok", last_synced_at: SYNCED },
    student: {
      specialty_name: "İqtisadiyyat",
      credits_earned: 30,
      cumulative_average: 78.4,
      synced_at: SYNCED,
    },
    semesters: [
      {
        semester_year: 2025,
        semester_term: "fall",
        credits_attempted: 10,
        credits_earned: 5,
        average: 74.5,
        courses: [
          course("SOS-1101", "Azərbaycan tarixi", 87, true),
          course("KAR-1101", "Karyera planlaşması-1", 42),
        ],
      },
    ],
    ...overrides,
  };
}

const APPEALS = {
  source: { state: "ok", last_synced_at: SYNCED },
  items: [
    {
      reference: "MQ-2025-5201-1",
      subject_code: "KAR-1101",
      subject_name: "Karyera planlaşması-1",
      semester_year: 2025,
      semester_term: "fall",
      status: "under_review",
      submitted_on: "2026-02-05",
      decided_on: null,
    },
  ],
};

describe("transcript", () => {
  it("shows the figures, the registry score with a marker, and the appeals", async () => {
    serve({
      "GET /api/v1/me/transcript": () => json(transcript()),
      "GET /api/v1/me/transcript/appeals": () => json(APPEALS),
    });
    wrap(<TranscriptPage />);

    expect(await screen.findByTestId("cabinet-average")).toHaveTextContent("78,40");
    expect(screen.getByTestId("cabinet-credits")).toHaveTextContent("30");
    expect(screen.getByText("Son sinxronizasiya:", { exact: false })).toBeInTheDocument();
    const row = screen.getByText("SOS-1101").closest("tr")!;
    expect(within(row).getByText("87")).toBeInTheDocument();
    expect(within(row).getByText("Fərq var")).toBeInTheDocument();
    expect(within(row).getByText("Keçib")).toBeInTheDocument();
    const failed = screen.getByText("KAR-1101", { selector: "span" }).closest("tr")!;
    expect(within(failed).getByText("Keçməyib")).toBeInTheDocument();
    expect(within(failed).queryByText("Fərq var")).not.toBeInTheDocument();
    expect(await screen.findByText("MQ-2025-5201-1")).toBeInTheDocument();
    expect(screen.getByText("Baxılır")).toBeInTheDocument();
  });

  it("tells a student the source is unavailable and from when the data is", async () => {
    serve({
      "GET /api/v1/me/transcript": () =>
        json(transcript({ source: { state: "unavailable", last_synced_at: SYNCED } })),
      "GET /api/v1/me/transcript/appeals": () => json(APPEALS),
    });
    wrap(<TranscriptPage />);

    const notice = await screen.findByTestId("cabinet-source-unavailable");
    expect(notice).toHaveTextContent("Mənbə əlçatan deyil");
    expect(notice).toHaveTextContent("4 Noyabr 2026, 02:40");
    expect(screen.getByTestId("cabinet-average")).toBeInTheDocument();
  });

  it("says so when nothing was ever synced or the person has no record", async () => {
    serve({
      "GET /api/v1/me/transcript": () =>
        json({
          source: { state: "never_synced", last_synced_at: null },
          student: null,
          semesters: [],
        }),
    });
    wrap(<TranscriptPage />);

    expect(await screen.findByTestId("cabinet-never-synced")).toBeInTheDocument();
    expect(screen.getByTestId("cabinet-empty")).toHaveTextContent("tapılmadı");
  });

  it("explains an unavailable source when there is no data at all", async () => {
    serve({
      "GET /api/v1/me/transcript": () =>
        json({
          source: { state: "unavailable", last_synced_at: null },
          student: null,
          semesters: [],
        }),
    });
    wrap(<TranscriptPage />);

    expect(await screen.findByTestId("cabinet-empty")).toHaveTextContent("əlaqə qurulmadığı");
    expect(screen.getByTestId("cabinet-source-unavailable")).toHaveTextContent("hələ heç bir");
  });

  it("offers a retry when loading fails", async () => {
    serve({ "GET /api/v1/me/transcript": () => json({ error: { code: "internal" } }, 500) });
    wrap(<TranscriptPage />);

    // The query client retries a failed read once before it gives up.
    expect(
      await screen.findByText(/Transkripti yükləmək alınmadı/, {}, { timeout: 4000 }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yenidən cəhd et" })).toBeInTheDocument();
  });

  it("shows the forbidden state on 403", async () => {
    serve({ "GET /api/v1/me/transcript": () => json({ error: { code: "auth.forbidden" } }, 403) });
    wrap(<TranscriptPage />);

    expect(
      await screen.findByRole("heading", { name: /icazəniz yoxdur/ }, { timeout: 4000 }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/yükləmək alınmadı/)).not.toBeInTheDocument();
  });
});

describe("ÜOMG card", () => {
  it("shows the cabinet figure beside the calculator, with the sync time and a link", async () => {
    serve({ "GET /api/v1/me/transcript": () => json(transcript()) });
    wrap(<CabinetCard />);

    expect(await screen.findByTestId("cabinet-card-average")).toHaveTextContent("78,40");
    expect(screen.getByRole("link", { name: "Transkripti aç" })).toHaveAttribute(
      "href",
      "/transcript",
    );
    expect(screen.getByText(/1 fənn üzrə|fənn üzrə reyestrdəki/)).toBeInTheDocument();
  });

  it("stays out of the way without a record or when the call fails", async () => {
    serve({
      "GET /api/v1/me/transcript": () =>
        json({ source: { state: "ok", last_synced_at: SYNCED }, student: null, semesters: [] }),
    });
    wrap(<CabinetCard />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.queryByText("Transkripti aç")).not.toBeInTheDocument();
  });
});

describe("staff sync page", () => {
  const RUNS = {
    source: { state: "unavailable", last_synced_at: SYNCED },
    items: [
      {
        id: "r2",
        trigger: "nightly",
        outcome: "failed",
        started_at: "2026-11-03T22:40:00Z",
        finished_at: "2026-11-03T22:41:00Z",
        students_synced: 0,
        students_not_found: 0,
        students_mismatched: 0,
        conflicts: 0,
        error_code: "cabinet.unavailable",
      },
      {
        id: "r1",
        trigger: "manual",
        outcome: "succeeded",
        started_at: "2026-11-02T22:40:00Z",
        finished_at: "2026-11-02T22:41:00Z",
        students_synced: 47,
        students_not_found: 1,
        students_mismatched: 0,
        conflicts: 2,
        error_code: null,
      },
    ],
  };
  const CONFLICTS = {
    items: [
      {
        university_id: "25765201",
        subject_code: "SOS-1101",
        semester_year: 2025,
        semester_term: "fall",
        detected_at: SYNCED,
      },
    ],
  };

  it("lists runs and conflicts with identifiers only, and starts a run", async () => {
    let started = 0;
    serve({
      "GET /api/v1/cabinet/sync-runs": () => json(RUNS),
      "GET /api/v1/cabinet/conflicts": () => json(CONFLICTS),
      "POST /api/v1/cabinet/sync-runs": () => {
        started += 1;
        return json({ queued: true }, 202);
      },
    });
    wrap(<SyncAdmin />);

    expect(await screen.findByText("Mənbə cavab vermədi")).toBeInTheDocument();
    expect(screen.getByText("Alınmadı")).toBeInTheDocument();
    expect(screen.getByText("Uğurlu")).toBeInTheDocument();
    expect(await screen.findByText("25765201")).toBeInTheDocument();
    expect(screen.getByText("SOS-1101")).toBeInTheDocument();
    expect(screen.queryByText(/Bal\b/)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "İndi sinxronlaşdır" }));
    await waitFor(() => expect(started).toBe(1));
    expect(await screen.findByText(/növbəyə qoyuldu/)).toBeInTheDocument();
  });

  it("says when there are no runs and no conflicts", async () => {
    serve({
      "GET /api/v1/cabinet/sync-runs": () =>
        json({ source: { state: "never_synced", last_synced_at: null }, items: [] }),
      "GET /api/v1/cabinet/conflicts": () => json({ items: [] }),
    });
    wrap(<SyncAdmin />);

    expect(await screen.findByText("Hələ sinxronizasiya aparılmayıb.")).toBeInTheDocument();
    expect(await screen.findByText("Fərq aşkarlanmayıb.")).toBeInTheDocument();
  });

  it("shows the forbidden state when the permission is missing", async () => {
    serve({
      "GET /api/v1/cabinet/sync-runs": () => json({ error: { code: "auth.forbidden" } }, 403),
      "GET /api/v1/cabinet/conflicts": () => json({ error: { code: "auth.forbidden" } }, 403),
    });
    wrap(<SyncAdmin />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: "İndi sinxronlaşdır" })).not.toBeInTheDocument();
  });
});
