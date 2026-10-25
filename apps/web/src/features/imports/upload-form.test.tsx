import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiProvider } from "@/lib/api/provider";
import { renderWithIntl } from "@/test/render";

import { UploadForm } from "./upload-form";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh: vi.fn() }) }));

const fetchMock = vi.fn<(request: Request) => Promise<Response>>();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  push.mockReset();
});

function renderForm() {
  return renderWithIntl(
    <ApiProvider csrfToken="csrf-0123">
      <UploadForm initialKind="students" />
    </ApiProvider>,
  );
}

function json(body: unknown, status: number) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("UploadForm", () => {
  it("asks for a file before uploading", async () => {
    renderForm();
    await userEvent.click(screen.getByRole("button", { name: "Faylı yoxlayın" }));
    expect(screen.getByText("Yoxlamaq üçün fayl seçin.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("offers the template of the chosen kind", async () => {
    renderForm();
    const template = screen.getByRole("link", { name: "Şablonu yükləyin (CSV)" });
    expect(template).toHaveAttribute("href", "/api/v1/admin/imports/templates/students");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: /Məlumat növü/ }), "groups");
    expect(template).toHaveAttribute("href", "/api/v1/admin/imports/templates/groups");
  });

  it("uploads with the CSRF token and opens the preview", async () => {
    fetchMock.mockResolvedValue(json({ id: "01a17008-23f6-71d3-983d-c217c01f7ba5" }, 201));
    renderForm();

    const file = new File(["university_id,family_name\n"], "telebeler-765a2.csv", {
      type: "text/csv",
    });
    await userEvent.upload(screen.getByLabelText(/^Fayl/, { selector: "input" }), file);
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Kodlaşdırma" }),
      "windows-1254",
    );
    await userEvent.click(screen.getByRole("button", { name: "Faylı yoxlayın" }));

    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/admin/imports/01a17008-23f6-71d3-983d-c217c01f7ba5"),
    );
    const request = fetchMock.mock.calls[0]![0];
    expect(request.method).toBe("POST");
    expect(new URL(request.url).pathname).toBe("/api/v1/admin/imports");
    expect(request.headers.get("x-csrf-token")).toBe("csrf-0123");
    expect(request.headers.get("content-type")).toMatch(/^multipart\/form-data; boundary=/);
    // jsdom's File is not Node's, so the file part arrives without content here; only its presence is checked.
    const body = await request.text();
    expect(body).toMatch(/name="kind"\s+students\s/);
    expect(body).toMatch(/name="encoding"\s+windows-1254\s/);
    expect(body).toContain('name="file"; filename=');
  });

  it("shows what went wrong when the file is refused", async () => {
    fetchMock.mockResolvedValue(
      json(
        {
          error: {
            code: "import.unsupported_format",
            message: "Bu fayl növü dəstəklənmir. CSV və ya XLSX faylı yükləyin.",
            details: {},
            request_id: "r1",
          },
        },
        422,
      ),
    );
    renderForm();
    await userEvent.upload(
      screen.getByLabelText(/^Fayl/, { selector: "input" }),
      new File(["%PDF"], "siyahı.xlsx", { type: "application/octet-stream" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Faylı yoxlayın" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Fayl yoxlanılmadı");
    expect(alert).toHaveTextContent("Bu fayl növü dəstəklənmir. CSV və ya XLSX faylı yükləyin.");
    expect(push).not.toHaveBeenCalled();
  });

  it("explains a network failure without internals", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    renderForm();
    await userEvent.upload(
      screen.getByLabelText(/^Fayl/, { selector: "input" }),
      new File(["code\n"], "f.csv", { type: "text/csv" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Faylı yoxlayın" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Serverlə əlaqə qurmaq mümkün olmadı.",
    );
  });
});
