import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { formatSize, uploadType } from "@/lib/uploads";
import { renderWithIntl } from "@/test/render";

import { Composer } from "./composer";
import { MessageAttachments, type Attachment } from "./message-attachments";
import { localProblem } from "./uploads";

function file(name: string, size = 10, type = ""): File {
  return new File([new Uint8Array(size)], name, { type });
}

function attachment(overrides: Partial<Attachment>): Attachment {
  return {
    id: crypto.randomUUID(),
    filename: "Mühazirə 3.pdf",
    mime: "application/pdf",
    size_bytes: 1_572_864,
    width: null,
    height: null,
    status: "clean",
    previewable: true,
    ...overrides,
  };
}

describe("upload checks", () => {
  it("decides the type by extension and refuses SVG, unknown and oversized files", () => {
    expect(uploadType(file("Hesabat.DOCX"))).toBe(
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    );
    expect(localProblem(file("sxem.svg", 10, "image/svg+xml"))).toBe(
      "chat.attachment_type_not_allowed",
    );
    expect(localProblem(file("adsiz"))).toBe("chat.attachment_type_not_allowed");
    expect(localProblem(file("böyük.zip", 25 * 1024 * 1024 + 1))).toBe("chat.attachment_too_large");
    expect(localProblem(file("boş.pdf", 0))).toBe("chat.attachment_too_large");
    expect(localProblem(file("lövhə.png"))).toBeNull();
    expect(formatSize(512)).toBe("512 B");
    expect(formatSize(1_572_864)).toBe("1,5 MB");
  });

  it("shows a refused file as a failed chip with the reason and lets it be removed", async () => {
    renderWithIntl(
      <ToastProvider>
        <Composer label="Mesaj" disabled={false} onSend={vi.fn()} attachTo="c-1" />
      </ToastProvider>,
    );
    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
    await userEvent.upload(input, file("sxem.svg", 10, "image/svg+xml"), { applyAccept: false });
    expect(
      screen.getByText("Bu fayl növü qəbul olunmur: şəkil, PDF, DOCX, PPTX və ya ZIP seçin."),
    ).toBeVisible();
    // A failed file alone is nothing to send.
    expect(screen.getByRole("button", { name: "Göndərin" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "sxem.svg faylını çıxarın" }));
    expect(screen.queryByText("sxem.svg")).toBeNull();
  });
});

describe("MessageAttachments", () => {
  it("shows scanning and rejected states to the uploader in words, not colour alone", () => {
    renderWithIntl(
      <ToastProvider>
        <MessageAttachments
          attachments={[
            attachment({ status: "pending", filename: "Konspekt.docx" }),
            attachment({ status: "infected", filename: "test.pdf" }),
            attachment({ status: "failed", filename: "Mühazirə.pdf" }),
            attachment({ filename: "Kurs işi.pdf" }),
          ]}
        />
      </ToastProvider>,
    );
    expect(screen.getByText("Fayl yoxlanılır…")).toBeVisible();
    expect(screen.getByText(/Faylda virus aşkarlandı/)).toBeVisible();
    expect(screen.getByText(/Fayl növü məzmununa uyğun deyil/)).toBeVisible();
    // Only the clean PDF offers a preview and a download.
    expect(screen.getAllByRole("button", { name: "Baxın" })).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Kurs işi.pdf faylını yükləyin" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "test.pdf faylını yükləyin" })).toBeNull();
  });
});
