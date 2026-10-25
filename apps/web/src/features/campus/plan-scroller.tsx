"use client";

import { useEffect, useRef, type ReactNode } from "react";

/**
 * Horizontal scroll frame for the floor plan. On narrow screens the plan is wider than the frame, so the selected
 * room is scrolled into the middle; only the frame moves, never the page.
 */
export function PlanScroller({ selected, children }: { selected?: string; children: ReactNode }) {
  const frame = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const container = frame.current;
    const room = selected
      ? container?.querySelector(`[data-room="${CSS.escape(selected)}"]`)
      : null;
    if (!container || !room) return;
    const box = room.getBoundingClientRect();
    const view = container.getBoundingClientRect();
    container.scrollLeft += box.left + box.width / 2 - (view.left + view.width / 2);
  }, [selected]);
  return (
    <div ref={frame} className="overflow-x-auto">
      {children}
    </div>
  );
}
