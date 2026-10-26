import { ApiRequestError, unwrap, type BrowserApi } from "@/lib/api/browser";

/** Mirrors the server's limits (D-068); the server checks again, this only spares a useless upload. */
export const MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024;
export const MAX_ATTACHMENTS = 10;
export const ACCEPTED_FILES = ".jpg,.jpeg,.png,.webp,.gif,.pdf,.docx,.pptx,.zip";

const EXTENSION_TYPES: Record<string, string> = {
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  webp: "image/webp",
  gif: "image/gif",
  pdf: "application/pdf",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  zip: "application/zip",
};

export type UploadState = "uploading" | "ready" | "failed";

export type Upload = {
  key: string;
  file: File;
  state: UploadState;
  /** 0–1 while uploading. */
  progress: number;
  attachmentId?: string;
  /** API code of the refusal, shown in plain words. */
  error?: string;
};

/**
 * The type the server will accept for this file. Browsers report some types inconsistently (or not at all for
 * DOCX on some systems), so the extension decides and the server compares it with the content.
 */
export function attachmentType(file: File): string | null {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  return EXTENSION_TYPES[extension] ?? null;
}

export function localProblem(file: File): string | null {
  if (!attachmentType(file)) return "chat.attachment_type_not_allowed";
  if (file.size === 0 || file.size > MAX_ATTACHMENT_BYTES) return "chat.attachment_too_large";
  return null;
}

/** Reserves the upload, then PUTs the file to the presigned URL with progress (fetch has none). */
export async function uploadAttachment(
  api: BrowserApi,
  channelId: string,
  file: File,
  onProgress: (fraction: number) => void,
  signal: AbortSignal,
): Promise<string> {
  const mime = attachmentType(file)!;
  const reserved = unwrap(
    await api.POST("/api/v1/chat/attachments/presign", {
      body: { channel_id: channelId, filename: file.name, mime, size: file.size },
    }),
  );
  await new Promise<void>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("PUT", reserved.url);
    for (const [name, value] of Object.entries(reserved.headers)) {
      request.setRequestHeader(name, value);
    }
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    request.onload = () =>
      request.status >= 200 && request.status < 300
        ? resolve()
        : reject(new ApiRequestError(request.status, "chat.attachments_unavailable", ""));
    request.onerror = () => reject(new ApiRequestError(0, "chat.attachments_unavailable", ""));
    request.onabort = () => reject(new DOMException("aborted", "AbortError"));
    signal.addEventListener("abort", () => request.abort(), { once: true });
    request.send(file);
  });
  return reserved.attachment_id;
}

const UNITS = ["B", "KB", "MB"] as const;

export function formatSize(bytes: number): string {
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const digits = unit === 0 || value >= 10 ? 0 : 1;
  // Written by hand: some browsers ship without Azerbaijani number data and would print "1.5".
  return `${value.toFixed(digits).replace(".", ",")} ${UNITS[unit]}`;
}
