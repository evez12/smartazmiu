"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiRequestError } from "@/lib/api/browser";
import { useOptionalApi } from "@/lib/api/provider";

import { localProblem, MAX_ATTACHMENTS, uploadAttachment, type Upload } from "./uploads";

/**
 * Files picked in the composer: each is reserved and uploaded at once, with progress, and can be removed
 * (which aborts it). An upload that is never sent is purged by the server after a day (D-068).
 */
export function useUploads(channelId: string | undefined) {
  const api = useOptionalApi();
  const [items, setItems] = useState<Upload[]>([]);
  const controllers = useRef(new Map<string, AbortController>());

  const patch = useCallback((key: string, change: Partial<Upload>) => {
    setItems((current) =>
      current.map((item) => (item.key === key ? { ...item, ...change } : item)),
    );
  }, []);

  const add = useCallback(
    (files: File[]) => {
      if (!channelId) return;
      const room = Math.max(0, MAX_ATTACHMENTS - items.length);
      const accepted = files.slice(0, room).map((file) => ({
        key: crypto.randomUUID(),
        file,
        state: "uploading" as const,
        progress: 0,
      }));
      setItems((current) => [...current, ...accepted]);
      for (const item of accepted) {
        const problem = localProblem(item.file);
        if (problem || !api) {
          patch(item.key, { state: "failed", error: problem ?? "chat.attachments_unavailable" });
          continue;
        }
        const controller = new AbortController();
        controllers.current.set(item.key, controller);
        uploadAttachment(
          api,
          channelId,
          item.file,
          (progress) => patch(item.key, { progress }),
          controller.signal,
        )
          .then((attachmentId) => patch(item.key, { state: "ready", progress: 1, attachmentId }))
          .catch((error: unknown) => {
            if (error instanceof DOMException && error.name === "AbortError") return;
            const code =
              error instanceof ApiRequestError ? error.code : "chat.attachments_unavailable";
            patch(item.key, { state: "failed", error: code });
          })
          .finally(() => controllers.current.delete(item.key));
      }
    },
    [api, channelId, items.length, patch],
  );

  const remove = useCallback((key: string) => {
    controllers.current.get(key)?.abort();
    setItems((current) => current.filter((item) => item.key !== key));
  }, []);

  const clear = useCallback(() => setItems([]), []);

  useEffect(() => {
    const running = controllers.current;
    return () => {
      for (const controller of running.values()) controller.abort();
    };
  }, []);

  return { items, add, remove, clear };
}
