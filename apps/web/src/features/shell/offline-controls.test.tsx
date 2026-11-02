import { act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NetworkProvider } from "@/components/ui/network";
import { ToastProvider } from "@/components/ui/toast";
import { Composer } from "@/features/chat/composer";
import { Rsvp } from "@/features/events/rsvp";
import type { EventItem } from "@/features/events/model";
import { FeedbackDialog } from "@/features/feedback/feedback-dialog";
import { NotificationSettingsForm } from "@/features/notifications/settings-form";
import { ProfileForm } from "@/features/profile/profile-form";
import { ReportDialog } from "@/features/reports/report-dialog";
import { ApiProvider } from "@/lib/api/provider";
import type { components } from "@/lib/api/schema";
import { renderWithIntl } from "@/test/render";

/*
 * §13.6: what needs the server is switched off while the browser is offline, with the reason in text. The examples
 * are the ones named in the Group B review: direct-message send (exempt, it queues), uploads, RSVP, reports and
 * profile edits, plus feedback and the notification settings.
 */
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/",
}));

const REASON = "İnternet bağlantısı olmadan bu əməliyyat mümkün deyil.";
const fetchMock = vi.fn<(request: Request) => Promise<Response>>();

function setOnline(value: boolean) {
  Object.defineProperty(navigator, "onLine", { configurable: true, get: () => value });
  window.dispatchEvent(new Event(value ? "online" : "offline"));
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  setOnline(false);
});
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  setOnline(true);
});

function renderOffline(ui: ReactElement) {
  return renderWithIntl(
    <NetworkProvider>
      <ApiProvider csrfToken="csrf-0123">
        <ToastProvider>{ui}</ToastProvider>
      </ApiProvider>
    </NetworkProvider>,
  );
}

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

function event(overrides: Partial<EventItem> = {}): EventItem {
  const start = new Date(Date.now() + 24 * 3600 * 1000).toISOString();
  return {
    id: "01a174e0-0000-7000-8000-000000000001",
    title: "Memarlıq sərgisi: tələbə layihələri",
    description: "",
    starts_at: start,
    ends_at: new Date(Date.parse(start) + 2 * 3600 * 1000).toISOString(),
    room: { code: "1-305", name: "Auditoriya" },
    location: "",
    capacity: 30,
    going: 12,
    spots_left: 18,
    audience: {
      type: "faculty",
      target_id: "f",
      label: "Tikinti iqtisadiyyatı fakültəsi",
      detail: "",
    },
    status: "published",
    version: 1,
    my_registration: null,
    ...overrides,
  };
}

describe("a screen offline", () => {
  it("switches off RSVP and does not send the request", async () => {
    renderOffline(<Rsvp event={event()} />);
    const register = screen.getByRole("button", { name: "Qeydiyyatdan keçin" });
    expect(register).toBeDisabled();
    expect(register).toHaveAttribute("title", REASON);
    await userEvent.click(register);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("lets the user open the withdraw question but not confirm it, with the reason beside the button", async () => {
    const going = event({
      my_registration: { status: "going", ticket_code: "SA1.x.y", checked_in_at: null },
    });
    renderOffline(<Rsvp event={going} />);
    await userEvent.click(screen.getByRole("button", { name: "Qeydiyyatı ləğv edin" }));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByRole("button", { name: "Qeydiyyatı ləğv edin" })).toBeDisabled();
    expect(within(dialog).getByText(REASON)).toBeVisible();
  });

  it("switches off saving a profile edit", () => {
    renderOffline(<ProfileForm profile={profile} />);
    expect(screen.getByRole("button", { name: "Yadda saxlayın" })).toBeDisabled();
  });

  it("switches off sending a report and says why inside the dialog", () => {
    renderOffline(
      <ReportDialog open onOpenChange={vi.fn()} targetType="message" targetId="1001" />,
    );
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("button", { name: "Şikayət göndərin" })).toBeDisabled();
    expect(within(dialog).getByText(REASON)).toBeVisible();
  });

  it("switches off feedback", () => {
    renderOffline(<FeedbackDialog open onOpenChange={vi.fn()} />);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("button", { name: "Göndərin" })).toBeDisabled();
    expect(within(dialog).getByText(REASON)).toBeVisible();
  });

  it("switches off saving the notification settings", () => {
    renderOffline(
      <NotificationSettingsForm
        settings={{
          categories: [
            { category: "announcements", push: true, email: true },
            { category: "events", push: true, email: false },
            { category: "schedule", push: true, email: false },
          ],
          quiet_hours: { enabled: true, starts_at: "23:00", ends_at: "08:00" },
          push_public_key: null,
          devices: 0,
        }}
      />,
    );
    expect(screen.getByRole("button", { name: "Yadda saxlayın" })).toBeDisabled();
  });

  it("keeps sending in a chat composer possible, because the message is queued and says so (§13.2, D-064)", async () => {
    const onSend = vi.fn();
    renderOffline(
      <Composer
        label="Mesaj"
        placeholder="Yazın"
        disabled={false}
        attachTo="c1"
        onSend={onSend}
        onTyping={vi.fn()}
      />,
    );
    await userEvent.type(screen.getByRole("combobox", { name: "Mesaj" }), "Sabah dərs var?");
    const send = screen.getByRole("button", { name: "Göndərin" });
    expect(send).toBeEnabled();
    await userEvent.click(send);
    expect(onSend).toHaveBeenCalledWith("Sabah dərs var?", []);
  });

  it("switches off attaching a file in the composer, because an upload needs the server", () => {
    renderOffline(
      <Composer
        label="Mesaj"
        placeholder="Yazın"
        disabled={false}
        attachTo="c1"
        onSend={vi.fn()}
        onTyping={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "Fayl əlavə edin" })).toBeDisabled();
  });

  it("switches everything back on when the connection returns", async () => {
    renderOffline(<ProfileForm profile={profile} />);
    const save = screen.getByRole("button", { name: "Yadda saxlayın" });
    expect(save).toBeDisabled();
    act(() => setOnline(true));
    expect(save).toBeEnabled();
  });
});
