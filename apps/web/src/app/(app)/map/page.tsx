import { MapPin, Search } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Field, Input } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import {
  FloorPlan,
  floorHref,
  RoomFacts,
  roomHref,
  type RoomData,
} from "@/features/campus/floor-plan";
import { ForbiddenState } from "@/features/shell/forbidden-state";
import { cn } from "@/lib/cn";
import { loaded, serverApi } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("map");
  return { title: t("title") };
}

type MapPageProps = {
  searchParams: Promise<{ room?: string; building?: string; floor?: string; q?: string }>;
};

const tabClasses =
  "-mb-px flex h-10 items-center pointer-coarse:h-11 border-b-2 border-transparent font-medium whitespace-nowrap text-muted transition-colors hover:text-text aria-[current=page]:border-primary aria-[current=page]:text-text";

export default async function MapPage({ searchParams }: MapPageProps) {
  const t = await getTranslations("map");
  const params = await searchParams;
  const api = await serverApi();
  const header = (
    <PageHeader
      title={t("title")}
      description={t("description")}
      breadcrumb={[{ label: t("title") }]}
    />
  );

  const buildings = await loaded(await api.GET("/api/v1/campus/buildings"));
  if (buildings.status === "forbidden") {
    return (
      <>
        {header}
        <ForbiddenState />
      </>
    );
  }
  const withFloors = buildings.data.filter((building) => building.floors.length > 0);
  if (withFloors.length === 0) {
    return (
      <>
        {header}
        <Panel>
          <PanelBody>
            <EmptyState className="py-0" icon={MapPin} message={t("empty")} />
          </PanelBody>
        </Panel>
      </>
    );
  }

  const roomCode = params.room?.trim().slice(0, 20);
  let selected: RoomData | null = null;
  if (roomCode) {
    const result = await api.GET("/api/v1/campus/rooms/{code}", {
      params: { path: { code: roomCode } },
    });
    // An unknown room is explained on the page instead of a 404: links to it may come from old timetables.
    if (result.response.status !== 404) {
      const room = await loaded(result);
      if (room.status === "ok") selected = room.data;
    }
  }
  const building =
    withFloors.find((b) => b.code === (selected?.building.code ?? params.building)) ??
    withFloors[0]!;
  const wantedLevel = selected?.floor.level ?? Number(params.floor);
  const floor = building.floors.find((f) => f.level === wantedLevel) ?? building.floors[0]!;

  const q = params.q?.trim().slice(0, 100) || undefined;
  const [plan, results] = await Promise.all([
    api
      .GET("/api/v1/campus/buildings/{building_code}/floors/{level}", {
        params: { path: { building_code: building.code, level: floor.level } },
      })
      .then(loaded),
    q ? api.GET("/api/v1/campus/rooms", { params: { query: { q } } }).then(loaded) : null,
  ]);
  if (plan.status === "forbidden" || results?.status === "forbidden") {
    return (
      <>
        {header}
        <ForbiddenState />
      </>
    );
  }

  return (
    <>
      {header}
      <div className="flex flex-col gap-6">
        <Panel>
          <form
            method="get"
            role="search"
            className="grid gap-4 p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start"
          >
            <Field label={t("searchLabel")} helper={t("searchHelper")}>
              <Input name="q" type="search" defaultValue={q ?? ""} autoComplete="off" />
            </Field>
            <Button type="submit" className="sm:mt-[26px]">
              <Icon icon={Search} />
              {t("search")}
            </Button>
          </form>
          {results ? (
            <section aria-label={t("results")} className="border-t border-border px-4 py-3">
              {results.data.length ? (
                <ul className="flex flex-col">
                  {results.data.map((room) => (
                    <li key={room.code} className="border-b border-border py-2 last:border-b-0">
                      <Link
                        href={roomHref(room.code)}
                        className="text-primary underline underline-offset-2 hover:text-primary-hover"
                      >
                        <span className="tabular">{room.code}</span>
                        {room.name ? ` · ${room.name}` : ""}
                      </Link>
                      <span className="text-sm text-muted">
                        {` · ${t(`types.${room.type}`)} · ${room.building.name}, ${room.floor.name}`}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted">{t("noResults")}</p>
              )}
            </section>
          ) : null}
        </Panel>

        {roomCode && !selected ? (
          <Banner tone="warning" title={t("roomNotFound", { room: roomCode })} />
        ) : null}

        <div className="flex flex-col gap-2">
          <nav aria-label={t("buildings")}>
            <ul className="flex gap-4 overflow-x-auto border-b border-border">
              {withFloors.map((item) => (
                <li key={item.code}>
                  <Link
                    href={floorHref(item.code, item.floors[0]!.level)}
                    aria-current={item.code === building.code ? "page" : undefined}
                    className={tabClasses}
                  >
                    {item.name}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <nav aria-label={t("floors")}>
            <ul className="flex flex-wrap gap-2 pt-2">
              {building.floors.map((item) => (
                <li key={item.level}>
                  <Link
                    href={floorHref(building.code, item.level)}
                    aria-current={item.level === floor.level ? "page" : undefined}
                    className={cn(
                      "inline-flex h-8 items-center rounded-control border border-border-control px-3 text-sm pointer-coarse:h-11",
                      "text-text transition-colors hover:bg-bg-subtle",
                      "aria-[current=page]:border-primary aria-[current=page]:bg-bg-subtle aria-[current=page]:font-medium",
                    )}
                  >
                    {item.name}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
          {/* min-w-0: the plan scrolls inside its panel instead of widening the page. */}
          <Panel className="min-w-0">
            <PanelHeader
              title={t("planTitle", { building: building.name, floor: floor.name })}
              description={t("planHint")}
            />
            <PanelBody>
              <FloorPlan plan={plan.data} selected={selected?.code} />
            </PanelBody>
          </Panel>
          <Panel aria-labelledby="selected-room">
            <PanelHeader titleId="selected-room" title={t("selectedRoom")} />
            <PanelBody>
              {selected ? (
                <RoomFacts room={selected} address={building.address} />
              ) : (
                <p className="text-muted">{t("noSelection")}</p>
              )}
            </PanelBody>
          </Panel>
        </div>
      </div>
    </>
  );
}
