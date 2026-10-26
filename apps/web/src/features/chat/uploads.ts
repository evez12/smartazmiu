import { unwrap, type BrowserApi } from "@/lib/api/browser";
import { putFile, uploadType } from "@/lib/uploads";

/** Mirrors the server's limits (D-068); the server checks again, this only spares a useless upload. */
export const MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024;
export const MAX_ATTACHMENTS = 10;

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

export function localProblem(file: File): string | null {
  if (!uploadType(file)) return "chat.attachment_type_not_allowed";
  if (file.size === 0 || file.size > MAX_ATTACHMENT_BYTES) return "chat.attachment_too_large";
  return null;
}

/** Reserves the upload, then PUTs the file to the presigned URL. */
export async function uploadAttachment(
  api: BrowserApi,
  channelId: string,
  file: File,
  onProgress: (fraction: number) => void,
  signal: AbortSignal,
): Promise<string> {
  const mime = uploadType(file)!;
  const reserved = unwrap(
    await api.POST("/api/v1/chat/attachments/presign", {
      body: { channel_id: channelId, filename: file.name, mime, size: file.size },
    }),
  );
  await putFile(
    reserved.url,
    reserved.headers,
    file,
    onProgress,
    signal,
    "chat.attachments_unavailable",
  );
  return reserved.attachment_id;
}
