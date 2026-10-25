import Link from "next/link";
import { useTranslations } from "next-intl";

import { cn } from "@/lib/cn";
import type { components } from "@/lib/api/schema";

import { PlanScroller } from "./plan-scroller";

export type FloorPlanData = components["schemas"]["FloorPlanOut"];
export type RoomData = components["schemas"]["RoomOut"];
export type Building = components["schemas"]["BuildingOut"];

export function roomHref(code: string): string {
  return `/map?room=${encodeURIComponent(code)}`;
}

export function floorHref(building: string, level: number): string {
  return `/map?building=${encodeURIComponent(building)}&floor=${level}`;
}

/**
 * The plan is drawn from room rectangles (DECISIONS D-042); no uploaded markup is rendered. Each room is a link,
 * so the plan works with the keyboard, and the selected room is marked by fill, outline and `aria-current`.
 */
export function FloorPlan({ plan, selected }: { plan: FloorPlanData; selected?: string }) {
  const t = useTranslations("map");
  const title = t("planTitle", { building: plan.building.name, floor: plan.name });
  return (
    // The plan keeps a readable scale on phones and scrolls inside its frame, never the page (§12.6).
    <PlanScroller selected={selected}>
      <svg
        viewBox={`0 0 ${plan.width} ${plan.height}`}
        className="block w-full min-w-[640px]"
        role="group"
        aria-label={title}
      >
        <rect
          x={0.5}
          y={0.5}
          width={plan.width - 1}
          height={plan.height - 1}
          className="fill-bg-subtle stroke-border-strong"
          vectorEffect="non-scaling-stroke"
        />
        {plan.rooms.map((room) => {
          const isSelected = room.code === selected;
          const isService = room.type === "service";
          return (
            <Link
              key={room.code}
              href={roomHref(room.code)}
              scroll={false}
              aria-label={t("roomLabel", { code: room.code, type: t(`types.${room.type}`) })}
              aria-current={isSelected ? "location" : undefined}
              data-room={room.code}
              className="group"
            >
              <rect
                x={room.x}
                y={room.y}
                width={room.width}
                height={room.height}
                vectorEffect="non-scaling-stroke"
                strokeWidth={isSelected ? 3 : 1}
                className={cn(
                  "transition-colors",
                  isSelected
                    ? "fill-primary stroke-primary"
                    : cn(
                        "stroke-border-strong group-hover:fill-bg-subtle",
                        isService ? "fill-bg-subtle" : "fill-surface",
                      ),
                )}
              />
              <text
                x={room.x + room.width / 2}
                y={room.y + room.height / 2}
                textAnchor="middle"
                dominantBaseline="central"
                className={cn(
                  "pointer-events-none text-[13px] tabular",
                  isSelected ? "fill-primary-contrast font-semibold" : "fill-text",
                  isService && !isSelected && "fill-muted",
                )}
              >
                {room.code}
              </text>
            </Link>
          );
        })}
      </svg>
    </PlanScroller>
  );
}

export function RoomFacts({ room, address }: { room: RoomData; address?: string }) {
  const t = useTranslations("map");
  const facts = [
    { label: t("facts.code"), value: room.code },
    ...(room.name ? [{ label: t("facts.name"), value: room.name }] : []),
    { label: t("facts.type"), value: t(`types.${room.type}`) },
    ...(room.capacity ? [{ label: t("facts.capacity"), value: String(room.capacity) }] : []),
    { label: t("facts.building"), value: room.building.name },
    { label: t("facts.floor"), value: room.floor.name },
    ...(address ? [{ label: t("facts.address"), value: address }] : []),
  ];
  return (
    <dl className="flex flex-col gap-3">
      {facts.map((fact) => (
        <div key={fact.label} className="flex flex-col">
          <dt className="text-sm text-muted">{fact.label}</dt>
          <dd className="break-words text-text tabular">{fact.value}</dd>
        </div>
      ))}
    </dl>
  );
}
