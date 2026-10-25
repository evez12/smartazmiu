import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { renderWithIntl } from "@/test/render";

import { Field, FileInput, Input, Select } from "./field";

describe("Field", () => {
  it("labels the control and links helper and error text", () => {
    renderWithIntl(
      <Field
        label="E-poçt"
        helper="Universitet ünvanı"
        error="E-poçt ünvanını daxil edin."
        required
      >
        <Input />
      </Field>,
    );
    const input = screen.getByRole("textbox", { name: /E-poçt/ });
    expect(input).toBeRequired();
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("E-poçt ünvanını daxil edin. Universitet ünvanı");
    expect(screen.getByText("(məcburi)")).toHaveClass("sr-only");
  });

  it("leaves a valid field without aria-invalid", () => {
    renderWithIntl(
      <Field label="Qrup">
        <Select defaultValue="765a2">
          <option value="765a2">765a2</option>
        </Select>
      </Field>,
    );
    expect(screen.getByRole("combobox", { name: "Qrup" })).not.toHaveAttribute("aria-invalid");
  });

  it("works standalone with explicit props", () => {
    renderWithIntl(<Input aria-label="Axtarış" />);
    expect(screen.getByRole("textbox", { name: "Axtarış" })).not.toBeRequired();
  });
});

describe("FileInput", () => {
  it("shows Azerbaijani labels and the chosen file name", async () => {
    const chosen: (File | null)[] = [];
    const { rerender } = renderWithIntl(
      <Field label="Fayl" helper="CSV və ya XLSX" required>
        <FileInput file={null} onFileChange={(file) => chosen.push(file)} />
      </Field>,
    );
    const input = screen.getByLabelText(/^Fayl/, { selector: "input" });
    expect(input).toBeRequired();
    expect(input).toHaveAccessibleDescription("CSV və ya XLSX");
    expect(screen.getByText("Fayl seçin")).toBeInTheDocument();
    expect(screen.getByText("Fayl seçilməyib")).toBeInTheDocument();

    const file = new File(["code,name_az\n"], "fakültələr.csv", { type: "text/csv" });
    await userEvent.upload(input, file);
    expect(chosen).toEqual([file]);

    rerender(
      <Field label="Fayl">
        <FileInput file={file} onFileChange={() => undefined} />
      </Field>,
    );
    expect(screen.getByText("fakültələr.csv")).toBeInTheDocument();
  });
});
