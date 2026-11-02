import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { Menu, MenuContent, MenuTrigger } from "@/components/ui/overlay";
import { ToastProvider } from "@/components/ui/toast";
import { LOCALE_COOKIE } from "@/i18n/config";
import { ApiProvider } from "@/lib/api/provider";
import { renderWithIntl } from "@/test/render";

import { LocaleMenuGroup, LocaleSync } from "./locale";

const router = { refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const fetchMock = vi.fn<(request: Request) => Promise<Response>>();
beforeEach(() => vi.stubGlobal("fetch", fetchMock));
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  router.refresh.mockReset();
  document.cookie = `${LOCALE_COOKIE}=; Max-Age=0; Path=/`;
});

function cookie(): string | undefined {
  return document.cookie
    .split("; ")
    .find((part) => part.startsWith(`${LOCALE_COOKIE}=`))
    ?.split("=")[1];
}

describe("LocaleSwitcher", () => {
  it("remembers the choice in a cookie and renders the page again", async () => {
    renderWithIntl(<LocaleSwitcher />, { locale: "en" });

    await userEvent.click(screen.getByRole("radio", { name: "Русский" }));

    expect(cookie()).toBe("ru");
    expect(router.refresh).toHaveBeenCalledOnce();
  });

  it("marks the current language and leaves it alone when pressed again", async () => {
    renderWithIntl(<LocaleSwitcher />, { locale: "ru" });

    const current = screen.getByRole("radio", { name: "Русский" });
    expect(current).toBeChecked();
    await userEvent.click(current);

    expect(cookie()).toBeUndefined();
    expect(router.refresh).not.toHaveBeenCalled();
  });
});

describe("LocaleMenuGroup", () => {
  function menu() {
    return renderWithIntl(
      <ApiProvider csrfToken="csrf-0123">
        <ToastProvider>
          <Menu open>
            <MenuTrigger>Menu</MenuTrigger>
            <MenuContent>
              <LocaleMenuGroup />
            </MenuContent>
          </Menu>
        </ToastProvider>
      </ApiProvider>,
      { locale: "en" },
    );
  }

  it("saves the language on the account before it switches", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    menu();

    await userEvent.click(screen.getByRole("menuitemradio", { name: "Русский" }));

    await waitFor(() => expect(router.refresh).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]![0];
    expect(request.method).toBe("PUT");
    expect(new URL(request.url).pathname).toBe("/api/v1/me/locale");
    expect(await request.json()).toEqual({ locale: "ru" });
    expect(cookie()).toBe("ru");
  });

  it("keeps the current language and says so when the account could not be updated", async () => {
    fetchMock.mockResolvedValue(
      Response.json({ error: { code: "server.internal_error", message: "x" } }, { status: 500 }),
    );
    menu();

    await userEvent.click(screen.getByRole("menuitemradio", { name: "Русский" }));

    expect(await screen.findByText("The language could not be changed. Try again.")).toBeVisible();
    expect(router.refresh).not.toHaveBeenCalled();
    expect(cookie()).toBeUndefined();
  });
});

describe("LocaleSync", () => {
  it("follows the language stored on the account when this device shows another one", () => {
    renderWithIntl(<LocaleSync preferred="ru" />, { locale: "az" });

    expect(cookie()).toBe("ru");
    expect(router.refresh).toHaveBeenCalledOnce();
  });

  it.each([["az"], [null], ["de"]])("does nothing for %s", (preferred) => {
    renderWithIntl(<LocaleSync preferred={preferred} />, { locale: "az" });

    expect(cookie()).toBeUndefined();
    expect(router.refresh).not.toHaveBeenCalled();
  });
});
