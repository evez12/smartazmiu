import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithIntl } from "@/test/render";

import { Button, networkDefault } from "./button";
import { Checkbox, Switch } from "./choice";
import { NetworkProvider } from "./network";
import { DialogContent, Dialog, Menu, MenuContent, MenuItem, MenuTrigger } from "./overlay";

const REASON = "İnternet bağlantısı olmadan bu əməliyyat mümkün deyil.";

function setOnline(value: boolean) {
  Object.defineProperty(navigator, "onLine", { configurable: true, get: () => value });
  window.dispatchEvent(new Event(value ? "online" : "offline"));
}

function renderOffline(ui: React.ReactElement) {
  setOnline(false);
  return renderWithIntl(<NetworkProvider>{ui}</NetworkProvider>);
}

afterEach(() => setOnline(true));

describe("what a button is when it says nothing", () => {
  it.each([
    [{ type: "submit" as const }, "required"],
    [{ variant: "primary" as const }, "required"],
    [{ variant: "destructive" as const }, "required"],
    [{ variant: "destructive-solid" as const }, "required"],
    [{ loading: false }, "required"],
    [{ loading: true }, "required"],
    [{ variant: "secondary" as const }, "local"],
    [{ variant: "tertiary" as const }, "local"],
    [{}, "local"],
  ])("%j is %s", (props, expected) => {
    expect(networkDefault(props)).toBe(expected);
  });
});

describe("buttons while offline", () => {
  it("switch off a main action and a submit with the reason as their title, and say so to the DOM", () => {
    renderOffline(
      <form>
        <Button variant="primary">Göndərin</Button>
        <Button type="submit" variant="secondary">
          Yadda saxlayın
        </Button>
      </form>,
    );
    for (const name of ["Göndərin", "Yadda saxlayın"]) {
      const button = screen.getByRole("button", { name });
      expect(button).toBeDisabled();
      expect(button).toHaveAttribute("title", REASON);
      expect(button).toHaveAttribute("data-offline");
    }
  });

  it("switch off an action that shows progress, a destructive one and one that says it needs the server", () => {
    renderOffline(
      <>
        <Button loading={false}>Daha çox yükləyin</Button>
        <Button variant="destructive">Silin</Button>
        <Button network="required" variant="tertiary">
          Bəyənin
        </Button>
      </>,
    );
    for (const name of ["Daha çox yükləyin", "Silin", "Bəyənin"]) {
      expect(screen.getByRole("button", { name })).toBeDisabled();
    }
  });

  it("leave a local button and a link alone", async () => {
    const onClick = vi.fn();
    renderOffline(
      <>
        <Button onClick={onClick}>Növbəti</Button>
        <Button variant="primary" network="local" onClick={onClick}>
          Hesablayın
        </Button>
        <Button asChild variant="primary">
          <a href="/schedule">Cədvəl</a>
        </Button>
      </>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Növbəti" }));
    await userEvent.click(screen.getByRole("button", { name: "Hesablayın" }));
    expect(onClick).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("link", { name: "Cədvəl" })).toBeEnabled();
  });

  it("do nothing when pressed offline, and work again when the connection returns", async () => {
    const onClick = vi.fn();
    renderOffline(
      <Button variant="primary" onClick={onClick}>
        Göndərin
      </Button>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Göndərin" }));
    expect(onClick).not.toHaveBeenCalled();

    act(() => setOnline(true));
    const button = screen.getByRole("button", { name: "Göndərin" });
    expect(button).toBeEnabled();
    expect(button).not.toHaveAttribute("title");
    await userEvent.click(button);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("are untouched outside the provider, so isolated components behave as before", () => {
    setOnline(false);
    renderWithIntl(<Button variant="primary">Göndərin</Button>);
    expect(screen.getByRole("button", { name: "Göndərin" })).toBeEnabled();
  });
});

describe("other controls while offline", () => {
  it("switch off a switch and a checkbox that save at once, not those that only fill in a form", () => {
    renderOffline(
      <>
        <Switch label="Dərhal saxlanan" network="required" checked={false} />
        <Switch label="Formun hissəsi" checked={false} />
        <Checkbox label="Dərhal saxlanan qutu" network="required" checked={false} />
        <Checkbox label="Formun qutusu" checked={false} />
      </>,
    );
    expect(screen.getByRole("switch", { name: "Dərhal saxlanan" })).toBeDisabled();
    expect(screen.getByRole("switch", { name: "Formun hissəsi" })).toBeEnabled();
    expect(screen.getByRole("checkbox", { name: "Dərhal saxlanan qutu" })).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: "Formun qutusu" })).toBeEnabled();
  });

  it("switch off a menu item that needs the server", async () => {
    renderOffline(
      <Menu>
        <MenuTrigger>Menyu</MenuTrigger>
        <MenuContent>
          <MenuItem network="required">Silin</MenuItem>
          <MenuItem>Bağlayın</MenuItem>
        </MenuContent>
      </Menu>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Menyu" }));
    expect(screen.getByRole("menuitem", { name: "Silin" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    expect(screen.getByRole("menuitem", { name: "Bağlayın" })).not.toHaveAttribute("aria-disabled");
  });

  it("show the reason as text in a dialog, where the page's banner is out of sight", () => {
    renderOffline(
      <Dialog open>
        <DialogContent title="Rəy bildirin" footer={<Button variant="primary">Göndərin</Button>}>
          Mətn
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByRole("status")).toHaveTextContent(REASON);
    expect(screen.getByRole("button", { name: "Göndərin" })).toBeDisabled();
  });

  it("show no note in a dialog while online", () => {
    setOnline(true);
    renderWithIntl(
      <NetworkProvider>
        <Dialog open>
          <DialogContent title="Rəy bildirin" footer={<Button variant="primary">Göndərin</Button>}>
            Mətn
          </DialogContent>
        </Dialog>
      </NetworkProvider>,
    );
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
