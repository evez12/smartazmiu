import { ApiRequestError } from "@/lib/api/browser";

/** Chat attachments and materials accept the same types (`app/core/uploads.py`). */
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

/**
 * The type the server will accept for this file. Browsers report some types inconsistently (or not at all for
 * DOCX on some systems), so the extension decides and the server compares it with the content.
 */
export function uploadType(file: File): string | null {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  return EXTENSION_TYPES[extension] ?? null;
}

/** PUTs a file to a presigned URL with progress (fetch has none); failures carry `failureCode`. */
export function putFile(
  url: string,
  headers: Record<string, string>,
  file: File,
  onProgress: (fraction: number) => void,
  signal: AbortSignal,
  failureCode: string,
): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("PUT", url);
    for (const [name, value] of Object.entries(headers)) {
      request.setRequestHeader(name, value);
    }
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    request.onload = () =>
      request.status >= 200 && request.status < 300
        ? resolve()
        : reject(new ApiRequestError(request.status, failureCode, ""));
    request.onerror = () => reject(new ApiRequestError(0, failureCode, ""));
    request.onabort = () => reject(new DOMException("aborted", "AbortError"));
    signal.addEventListener("abort", () => request.abort(), { once: true });
    request.send(file);
  });
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
