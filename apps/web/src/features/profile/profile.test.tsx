import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { ApiProvider } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";
import { renderWithIntl } from "@/test/render";

import { PhotoControls } from "./photo-controls";
import { ProfileForm } from "./profile-form";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh }) }));

const fetchMock = vi.fn<(request: Request) => Promise<Response>>();

beforeEach(() => vi.stubGlobal("fetch", fetchMock));
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  refresh.mockReset();
});

const profile: components["schemas"]["ProfileOut"] = {
  id: "01a1",
  display_name: "Aysel Məmmədova",
  given_name: "Aysel",
  family_name: "Məmmədova",
  email: "aysel.mammadova@smartazmiu.test",
  university_id: "25765201",
  person_type: "student",
  bio: "",
  photo_url: null,
  dm_policy: "shared_context",
  contact_visibility: "hidden",
  version: 3,
};

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

describe("ProfileForm", () => {
  it("saves bio and privacy settings with the edited version", async () => {
    fetchMock.mockResolvedValue(json({ ...profile, version: 4 }));
    renderInApp(<ProfileForm profile={profile} />);

    await userEvent.type(screen.getByRole("textbox", { name: "Haqqınızda" }), "Statistika");
    expect(screen.getByText("10 / 300")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("radio", { name: "Heç kim", description: /Müəllimlər/ }),
    );
    await userEvent.click(screen.getByRole("radio", { name: "Bütün istifadəçilər" }));
    await userEvent.click(screen.getByRole("button", { name: "Yadda saxlayın" }));

    await waitFor(() => expect(refresh).toHaveBeenCalled());
    const request = fetchMock.mock.calls[0]![0];
    expect(request.method).toBe("PATCH");
    expect(request.headers.get("x-csrf-token")).toBe("csrf-0123");
    expect(await request.json()).toEqual({
      version: 3,
      bio: "Statistika",
      dm_policy: "nobody",
      contact_visibility: "everyone",
    });
    expect(await screen.findByText("Profil yadda saxlanıldı")).toBeInTheDocument();
  });

  it("blocks a bio over 300 characters", async () => {
    renderInApp(<ProfileForm profile={{ ...profile, bio: "ə".repeat(301) }} />);
    expect(screen.getByText("Mətn 300 simvoldan uzundur. Qısaldın.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yadda saxlayın" })).toBeDisabled();
  });

  it("explains a conflicting edit and offers a reload", async () => {
    fetchMock.mockResolvedValue(
      json(
        {
          error: {
            code: "profile.version_conflict",
            message:
              "Profil başqa pəncərədə dəyişdirilib. Səhifəni yeniləyib dəyişiklikləri yenidən edin.",
            details: { version: 4 },
            request_id: "r1",
          },
        },
        409,
      ),
    );
    renderInApp(<ProfileForm profile={profile} />);
    await userEvent.click(screen.getByRole("button", { name: "Yadda saxlayın" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Profil başqa pəncərədə dəyişdirilib.");
    expect(screen.getByRole("button", { name: "Səhifəni yeniləyin" })).toBeInTheDocument();
    expect(refresh).not.toHaveBeenCalled();
  });
});

describe("PhotoControls", () => {
  it("uploads a chosen photo right away", async () => {
    fetchMock.mockResolvedValue(json({ ...profile, photo_url: "/api/v1/users/01a1/photo?v=1" }));
    renderInApp(<PhotoControls displayName="Aysel Məmmədova" photoUrl={null} />);

    const picker = screen.getByLabelText("Şəkil yükləyin");
    expect(picker).toHaveAccessibleDescription(/JPEG, PNG və ya WebP/);
    await userEvent.upload(picker, new File(["jpeg"], "foto.jpg", { type: "image/jpeg" }));

    await waitFor(() => expect(refresh).toHaveBeenCalled());
    const request = fetchMock.mock.calls[0]![0];
    expect(request.method).toBe("PUT");
    expect(new URL(request.url).pathname).toBe("/api/v1/me/photo");
    expect(request.headers.get("x-csrf-token")).toBe("csrf-0123");
    expect(screen.queryByRole("button", { name: "Şəkli silin" })).not.toBeInTheDocument();
  });

  it("removes the photo only after confirmation", async () => {
    fetchMock.mockResolvedValue(json(profile));
    renderInApp(
      <PhotoControls displayName="Aysel Məmmədova" photoUrl="/api/v1/users/01a1/photo?v=1" />,
    );
    expect(screen.getByLabelText("Şəkli dəyişin")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Şəkli silin" }));
    const dialog = screen.getByRole("alertdialog", { name: "Şəkli silmək istəyirsiniz?" });
    expect(fetchMock).not.toHaveBeenCalled();
    await userEvent.click(
      Array.from(dialog.querySelectorAll("button")).find((b) => b.textContent === "Şəkli silin")!,
    );

    await waitFor(() => expect(refresh).toHaveBeenCalled());
    expect(fetchMock.mock.calls[0]![0].method).toBe("DELETE");
  });

  it("shows why an upload failed", async () => {
    fetchMock.mockResolvedValue(
      json(
        {
          error: {
            code: "photo.invalid_image",
            message: "Şəkil oxunmadı. JPEG, PNG və ya WebP formatında şəkil seçin.",
            details: {},
            request_id: "r2",
          },
        },
        422,
      ),
    );
    renderInApp(<PhotoControls displayName="Aysel Məmmədova" photoUrl={null} />);
    await userEvent.upload(
      screen.getByLabelText("Şəkil yükləyin"),
      new File(["x"], "foto.png", { type: "image/png" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("Şəkil oxunmadı.");
  });
});
