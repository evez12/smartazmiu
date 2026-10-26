import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { ApiProvider } from "@/lib/api/provider";
import { renderWithIntl } from "@/test/render";

import { MaterialActions } from "./material-actions";
import { MaterialReportTable, type MaterialReportItem } from "./material-report-table";
import { MaterialTable } from "./material-table";
import type { Material, MaterialVersion } from "./model";
import { UploadForm } from "./upload-form";

const router = { refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const fetchMock = vi.fn<(request: Request) => Promise<Response>>();
const puts: { url: string; type: string | null }[] = [];

/** The presigned PUT goes through XMLHttpRequest for progress; this stands in for storage. */
class FakeUpload {
  status = 200;
  upload: { onprogress: ((event: ProgressEvent) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  private url = "";
  private headers: Record<string, string> = {};
  open(_method: string, url: string) {
    this.url = url;
  }
  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }
  abort() {}
  send() {
    puts.push({ url: this.url, type: this.headers["Content-Type"] ?? null });
    queueMicrotask(() => this.onload?.());
  }
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("XMLHttpRequest", FakeUpload);
});
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  router.push.mockReset();
  puts.length = 0;
});

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function wrap(ui: React.ReactNode) {
  return renderWithIntl(
    <ApiProvider csrfToken="csrf-0123">
      <ToastProvider>{ui}</ToastProvider>
    </ApiProvider>,
  );
}

const LEYLA = { id: "u-leyla", display_name: "Leyla Həsənova" };
const FALL = { id: "s-2026", label: "2026 Payız", can_upload: true };

function version(overrides: Partial<MaterialVersion> = {}): MaterialVersion {
  return {
    id: crypto.randomUUID(),
    version: 1,
    filename: "Mühazirə 1.pdf",
    mime: "application/pdf",
    size_bytes: 1_572_864,
    note: "",
    status: "clean",
    previewable: true,
    uploaded_by: LEYLA,
    created_at: "2026-10-20T06:00:00Z",
    ...overrides,
  };
}

function material(overrides: Partial<Material> = {}): Material {
  return {
    id: crypto.randomUUID(),
    subject_id: "subj-1",
    semester: FALL,
    type: "lecture",
    title: "Təsviri statistika",
    description: "",
    created_by: LEYLA,
    created_at: "2026-10-20T06:00:00Z",
    current: version(),
    version_count: 1,
    scanning: false,
    hidden: false,
    can_edit: false,
    ...overrides,
  };
}

describe("MaterialTable", () => {
  it("lists materials with type, file and states in words", () => {
    wrap(
      <MaterialTable
        caption="Materiallar"
        showSemester
        items={[
          material(),
          material({ title: "Sillabus", type: "syllabus", current: null, scanning: true }),
          material({ title: "Köhnə mühazirə", hidden: true }),
        ]}
      />,
    );
    expect(screen.getByRole("link", { name: "Təsviri statistika" })).toHaveAttribute(
      "href",
      expect.stringMatching(/^\/materials\/subj-1\//),
    );
    expect(screen.getAllByText("Mühazirə")).toHaveLength(2);
    expect(screen.getByText("Fayl hələ yoxlanılır")).toBeVisible();
    expect(screen.getByText("Yoxlanılır")).toBeVisible();
    expect(screen.getByText("Gizlədilib")).toBeVisible();
    expect(screen.getAllByText("2026 Payız")).toHaveLength(3);
    expect(screen.getAllByText(/1,5 MB · 1 versiya/)).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: "Baxın" })).toHaveLength(2);
  });

  it("downloads through a fresh one-minute link", async () => {
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign, origin: "http://localhost" });
    fetchMock.mockResolvedValue(json({ url: "/smartazmiu/x", expires_at: "2026-10-26T10:01:00Z" }));
    wrap(<MaterialTable caption="Materiallar" showSemester={false} items={[material()]} />);
    await userEvent.click(screen.getByRole("button", { name: "Mühazirə 1.pdf faylını endirin" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("/smartazmiu/x"));
    expect(new URL(fetchMock.mock.calls[0]![0].url).searchParams.get("inline")).toBe("false");
  });
});

describe("UploadForm", () => {
  it("explains every missing field inline before uploading anything", async () => {
    wrap(<UploadForm mode="material" subjectId="subj-1" semesters={[FALL]} />);
    await userEvent.click(screen.getByRole("button", { name: "Yükləyin" }));
    expect(screen.getByText("Materialın növünü seçin.")).toBeVisible();
    expect(screen.getByText("Materialın adını yazın.")).toBeVisible();
    expect(screen.getByText("Faylı seçin.")).toBeVisible();
    expect(screen.getByText("Faylı paylaşmaq hüququnuzu təsdiq edin.")).toBeVisible();
    // The only semester the teacher may upload for is chosen already.
    expect(screen.queryByText("Semestri seçin.")).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();

    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
    await userEvent.upload(input, new File(["x"], "sxem.svg"), { applyAccept: false });
    await userEvent.click(screen.getByRole("button", { name: "Yükləyin" }));
    expect(
      screen.getByText("Bu fayl növü qəbul olunmur: PDF, DOCX, PPTX, ZIP və ya şəkil seçin."),
    ).toBeVisible();
  });

  it("uploads the file, saves the form with consent and opens the material", async () => {
    fetchMock.mockImplementation(async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/materials/uploads/presign") {
        return json({
          upload_id: "up-1",
          url: "/smartazmiu/materials/k?sig=1",
          object_key: "materials/k",
          expires_at: "2026-10-26T10:10:00Z",
          headers: { "Content-Type": "application/pdf" },
        });
      }
      return json({ ...material({ id: "m-1" }), subject_name: "Statistika", versions: [] }, 201);
    });
    wrap(<UploadForm mode="material" subjectId="subj-1" semesters={[FALL]} />);
    await userEvent.selectOptions(screen.getByLabelText(/^Növ/), "seminar");
    await userEvent.type(screen.getByLabelText(/^Ad/), "  Seminar 2 ");
    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
    await userEvent.upload(input, new File(["%PDF-1.7"], "Seminar 2.pdf"));
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: "Yükləyin" }));

    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/materials/subj-1/m-1"));
    expect(puts).toEqual([{ url: "/smartazmiu/materials/k?sig=1", type: "application/pdf" }]);
    const [presign, save] = fetchMock.mock.calls.map(([request]) => request);
    expect(await presign!.json()).toEqual({
      subject_id: "subj-1",
      semester_id: "s-2026",
      filename: "Seminar 2.pdf",
      mime: "application/pdf",
      size: 8,
    });
    expect(await save!.json()).toEqual({
      upload_id: "up-1",
      type: "seminar",
      title: "Seminar 2",
      description: "",
      copyright_confirmed: true,
    });
  });

  it("adds a version with a note and shows the server's refusal", async () => {
    fetchMock.mockResolvedValue(
      json(
        {
          error: {
            code: "materials.upload_not_allowed",
            message: "Bu fənn və semestr üçün material yükləmək icazəniz yoxdur.",
            details: {},
            request_id: "r",
          },
        },
        403,
      ),
    );
    wrap(<UploadForm mode="version" subjectId="subj-1" semesterId="s-2026" materialId="m-1" />);
    await userEvent.type(screen.getByLabelText(/Nə dəyişib/), "Düzəliş");
    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
    await userEvent.upload(input, new File(["%PDF-1.7"], "v2.pdf"));
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: "Yükləyin" }));
    expect(
      await screen.findByText("Bu fənn və semestr üçün material yükləmək icazəniz yoxdur."),
    ).toBeVisible();
    expect(puts).toEqual([]);
  });
});

describe("MaterialActions", () => {
  it("reports a material once a reason is chosen", async () => {
    fetchMock.mockResolvedValue(json({ id: "r-1", status: "open", duplicate: false }, 201));
    wrap(<MaterialActions materialId="m-1" hidden={false} canManage={false} />);
    expect(screen.queryByRole("button", { name: "Gizlədin" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Şikayət edin" }));
    await userEvent.click(screen.getByRole("radio", { name: "Müəllif hüququ pozulub" }));
    await userEvent.click(screen.getByRole("button", { name: "Şikayət göndərin" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const request = fetchMock.mock.calls[0]![0];
    expect(new URL(request.url).pathname).toBe("/api/v1/materials/m-1/reports");
    expect(await request.json()).toEqual({ reason: "copyright", note: "" });
  });

  it("lets staff hide a material after confirming, and show it again", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    const { unmount } = wrap(<MaterialActions materialId="m-1" hidden={false} canManage />);
    await userEvent.click(screen.getByRole("button", { name: "Gizlədin" }));
    expect(screen.getByRole("alertdialog")).toHaveTextContent("Fayllar və versiyalar silinmir");
    await userEvent.click(screen.getAllByRole("button", { name: "Gizlədin" }).at(-1)!);
    await waitFor(() => expect(router.refresh).toHaveBeenCalled());
    expect(await fetchMock.mock.calls[0]![0].json()).toEqual({ hidden: true });
    unmount();

    wrap(<MaterialActions materialId="m-1" hidden canManage />);
    await userEvent.click(screen.getByRole("button", { name: "Yenidən göstərin" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(await fetchMock.mock.calls[1]![0].json()).toEqual({ hidden: false });
  });
});

describe("MaterialReportTable", () => {
  const report: MaterialReportItem = {
    id: "mr-1",
    material_id: "m-1",
    material_title: "Təsviri statistika",
    subject_id: "subj-1",
    subject_name: "Statistika",
    material_hidden: true,
    reason: "copyright",
    note: "Kitabdan skan",
    status: "open",
    reporter: { id: "u-aysel", display_name: "Aysel Məmmədova" },
    handled_by: null,
    handled_at: null,
    created_at: "2026-10-26T08:00:00Z",
  };

  it("shows the material, reason and status, and closes a report", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    wrap(<MaterialReportTable items={[report]} canHandle />);
    expect(screen.getByRole("link", { name: "Statistika · Təsviri statistika" })).toHaveAttribute(
      "href",
      "/materials/subj-1/m-1",
    );
    expect(screen.getByText("Gizlədilib")).toBeVisible();
    expect(screen.getByText("Müəllif hüququ pozulub")).toBeVisible();
    expect(screen.getByText("Qeyd: Kitabdan skan")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Rədd edin" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const request = fetchMock.mock.calls[0]![0];
    expect(new URL(request.url).pathname).toBe("/api/v1/moderation/material-reports/mr-1");
    expect(await request.json()).toEqual({ status: "dismissed" });
  });
});
