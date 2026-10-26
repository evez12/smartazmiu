"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import { useTranslations } from "next-intl";
import { useEffect, useLayoutEffect, useRef } from "react";

import { Button } from "@/components/ui/button";

import { TimelineRow, type RowContext } from "./message-row";
import type { TimelineItem } from "./model";

type MessageListProps = {
  label: string;
  items: TimelineItem[];
  hasOlder: boolean;
  hasNewer: boolean;
  loadingOlder: boolean;
  onLoadOlder: () => void;
  onLoadNewer: () => void;
  onBottomChange: (atBottom: boolean) => void;
  context: RowContext;
  blockedIds: ReadonlySet<string>;
  onRetry: (clientMsgId: string) => void;
};

const NEAR_EDGE_PX = 120;

/**
 * Virtualized history (only the rows in view are rendered). It sticks to the newest message while the reader is
 * at the bottom, keeps the reading position when older pages are prepended, and loads more at either edge.
 */
export function MessageList({
  label,
  items,
  hasOlder,
  hasNewer,
  loadingOlder,
  onLoadOlder,
  onLoadNewer,
  onBottomChange,
  context,
  blockedIds,
  onRetry,
}: MessageListProps) {
  const t = useTranslations("chat");
  const scroller = useRef<HTMLDivElement>(null);
  const atBottom = useRef(true);
  const firstKey = useRef<string | null>(null);
  // TanStack Virtual keeps its own mutable state, which the React Compiler cannot memoise; it skips this one.
  // eslint-disable-next-line react-hooks/incompatible-library
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => 52,
    overscan: 12,
    getItemKey: (index) => items[index]!.key,
  });

  // Prepended history: keep the previously first row where the reader left it.
  useLayoutEffect(() => {
    const previousFirst = firstKey.current;
    firstKey.current = items[0]?.key ?? null;
    if (previousFirst && items[0]?.key !== previousFirst) {
      const index = items.findIndex((item) => item.key === previousFirst);
      if (index > 0) {
        virtualizer.scrollToIndex(index, { align: "start" });
        return;
      }
    }
    if (atBottom.current && items.length)
      virtualizer.scrollToIndex(items.length - 1, { align: "end" });
  }, [items, virtualizer]);

  useEffect(() => {
    const element = scroller.current;
    if (!element) return;
    const onScroll = () => {
      const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
      const bottom = distance < NEAR_EDGE_PX;
      if (bottom !== atBottom.current) {
        atBottom.current = bottom;
        onBottomChange(bottom);
      }
      if (element.scrollTop < NEAR_EDGE_PX && hasOlder && !loadingOlder) onLoadOlder();
      if (bottom && hasNewer) onLoadNewer();
    };
    element.addEventListener("scroll", onScroll, { passive: true });
    return () => element.removeEventListener("scroll", onScroll);
  }, [hasNewer, hasOlder, loadingOlder, onBottomChange, onLoadNewer, onLoadOlder]);

  return (
    <div
      ref={scroller}
      role="log"
      aria-label={label}
      aria-live="polite"
      aria-relevant="additions"
      tabIndex={0}
      className="focus-visible:ring-focus-ring min-h-0 flex-1 overflow-y-auto outline-none focus-visible:ring-2 focus-visible:ring-inset"
    >
      {hasOlder ? (
        <div className="flex justify-center py-2">
          {/* Keyboard and screen-reader users load history explicitly; scrolling does it for others. */}
          <Button size="dense" variant="tertiary" loading={loadingOlder} onClick={onLoadOlder}>
            {t("loadOlder")}
          </Button>
        </div>
      ) : null}
      <div className="relative w-full" style={{ height: virtualizer.getTotalSize() }}>
        {virtualizer.getVirtualItems().map((row) => (
          <div
            key={row.key}
            data-index={row.index}
            ref={virtualizer.measureElement}
            className="absolute top-0 left-0 w-full"
            style={{ transform: `translateY(${row.start}px)` }}
          >
            <TimelineRow
              item={items[row.index]!}
              context={context}
              blockedIds={blockedIds}
              onRetry={onRetry}
            />
          </div>
        ))}
      </div>
      {hasNewer ? (
        <div className="flex justify-center py-2">
          <Button size="dense" variant="tertiary" onClick={onLoadNewer}>
            {t("loadNewer")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
