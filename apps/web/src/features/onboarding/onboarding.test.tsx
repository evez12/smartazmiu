import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { ApiProvider } from "@/lib/api/provider";
import { renderWithIntl } from "@/test/render";

import { OnboardingTour, RestartTourButton } from "./onboarding-tour";
import { tourSteps } from "./steps";

const router = { refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const fetchMock = vi.fn<(request: Request) => Promise<Response>>();
beforeEach(() => vi.stubGlobal("fetch", fetchMock));
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  router.push.mockReset();
  router.refresh.mockReset();
});

function wrap(ui: React.ReactNode) {
  return renderWithIntl(
    <ApiProvider csrfToken="csrf-0123">
      <ToastProvider>{ui}</ToastProvider>
    </ApiProvider>,
  );
}

describe("tourSteps", () => {
  it("follows the user's main capacity", () => {
    expect(tourSteps(["student"]).map((step) => step.key)).toEqual([
      "schedule",
      "chat",
      "materials",
      "notifications",
      "profile",
    ]);
    expect(tourSteps(["teacher"]).map((step) => step.key)).toContain("materialsTeacher");
    expect(tourSteps(["student", "staff"]).map((step) => step.href)).toEqual([
      "/admin/imports",
      "/announcements",
      "/admin/reports",
      "/profile",
    ]);
  });
});

describe("OnboardingTour", () => {
  it("walks through the steps and stores the finish once", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    wrap(<OnboardingTour roles={["student"]} />);
    expect(screen.getByText("Addım 1 / 5")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Dərs cədvəli" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Bölməyə keçin" })).toHaveAttribute(
      "href",
      "/schedule",
    );
    expect(screen.queryByRole("button", { name: "Əvvəlki" })).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Növbəti" }));
    expect(screen.getByRole("heading", { name: "Fənn və qrup kanalları" })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Əvvəlki" }));
    expect(screen.getByText("Addım 1 / 5")).toBeVisible();
    for (let step = 0; step < 4; step += 1) {
      await userEvent.click(screen.getByRole("button", { name: "Növbəti" }));
    }
    expect(screen.getByRole("heading", { name: "Profil və məxfilik" })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Bitirin" }));

    await waitFor(() => expect(router.refresh).toHaveBeenCalled());
    expect(screen.queryByText("SmartAzMİU ilə tanışlıq")).toBeNull();
    const request = fetchMock.mock.calls[0]![0];
    expect(request.method).toBe("PUT");
    expect(new URL(request.url).pathname).toBe("/api/v1/me/onboarding");
    expect(await request.json()).toEqual({ done: true });
  });

  it("comes back with a message when closing it could not be saved", async () => {
    fetchMock.mockRejectedValue(new TypeError("offline"));
    wrap(<OnboardingTour roles={["teacher"]} />);
    await userEvent.click(screen.getByRole("button", { name: "Tanışlığı bağlayın" }));
    expect(await screen.findByText("Seçiminiz saxlanılmadı. Yenidən cəhd edin.")).toBeVisible();
    expect(screen.getByText("SmartAzMİU ilə tanışlıq")).toBeVisible();
  });
});

describe("RestartTourButton", () => {
  it("shows the tour again on the dashboard", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    wrap(<RestartTourButton />);
    await userEvent.click(screen.getByRole("button", { name: "Tanışlıq turunu yenidən göstərin" }));
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/"));
    expect(await fetchMock.mock.calls[0]![0].json()).toEqual({ done: false });
  });
});
