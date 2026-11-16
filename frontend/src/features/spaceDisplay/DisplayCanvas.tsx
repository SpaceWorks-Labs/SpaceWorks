import "./display.css";
import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { AnnouncementPanel, CalendarPanel, HereNowPanel, MachinesPanel } from "./DisplayPanels";
import { OpeningHoursPanel, PublicStatsPanel } from "./DisplayPanelsMore";
import { InventoryHighlightsPanel, SponsorsPanel } from "./DisplayPanelsExtra";
import { availablePanels } from "./useDisplayScreen";
import type { DisplayPanel, DisplayState } from "./api";

type Paired = Extract<DisplayState, { state: "paired" }>;

/** Index of the slide on screen. One timeout per slide (not an interval), so each panel keeps its own seconds. */
export function usePlaylist(panels: DisplayPanel[], seconds: Paired["config"]["slide_seconds"], fallback: number, paused = false): number {
  const [index, setIndex] = useState(0);
  const count = panels.length;
  const current = count ? index % count : 0;
  const panel = panels[current];
  useEffect(() => {
    if (count <= 1 || paused) return;
    const wait = Math.max(5, seconds[panel] ?? fallback) * 1000;
    const id = window.setTimeout(() => setIndex((old) => (old + 1) % count), wait);
    return () => window.clearTimeout(id);
  }, [count, current, panel, seconds, fallback, paused]);
  return current;
}

function Slide({ panel, state, now }: { panel: DisplayPanel; state: Paired; now: number }) {
  const zone = state.space.timezone || "UTC";
  if (panel === "here_now" && state.here_now) return <HereNowPanel data={state.here_now} />;
  if (panel === "calendar" && state.calendar) return <CalendarPanel data={state.calendar} timeZone={zone} now={now} />;
  if (panel === "machines" && state.machines) return <MachinesPanel data={state.machines} />;
  if (panel === "announcement" && state.announcement) return <AnnouncementPanel text={state.announcement} />;
  if (panel === "public_stats" && state.public_stats) return <PublicStatsPanel data={state.public_stats} />;
  if (panel === "opening_hours" && state.opening_hours) return <OpeningHoursPanel data={state.opening_hours} />;
  if (panel === "inventory_highlights" && state.inventory_highlights) return <InventoryHighlightsPanel data={state.inventory_highlights} />;
  if (panel === "sponsors" && state.sponsors) return <SponsorsPanel data={state.sponsors} />;
  return null;
}

/**
 * The screen's body for its chosen layout: `single` shows the first available panel and stays on it,
 * `grid` shows every panel at once, `playlist` rotates one panel at a time using each panel's seconds.
 * Panels only ever fade (CSS opacity, once per slide): no loops, so an Anthias Pi stays cool.
 */
export function DisplayCanvas({ state, now, paused = false }: { state: Paired; now: number; paused?: boolean }) {
  const panels = availablePanels(state);
  const { layout, slide_seconds: slides, rotation_seconds: fallback } = state.config;
  const index = usePlaylist(layout === "playlist" ? panels : [], slides ?? {}, fallback, paused);
  if (!panels.length) return <p className="text-3xl text-muted" role="status">{t`Nothing to show right now.`}</p>;
  if (layout === "grid") {
    return <div className="grid gap-10 xl:grid-cols-2">{panels.map((panel) => <div key={panel} className="min-w-0"><Slide panel={panel} state={state} now={now} /></div>)}</div>;
  }
  const panel = layout === "single" ? panels[0] : panels[index];
  return <div key={panel} className="sw-display-fade"><Slide panel={panel} state={state} now={now} /></div>;
}
