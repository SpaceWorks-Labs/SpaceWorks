import { t } from "@lingui/core/macro";
import { useState, type KeyboardEvent } from "react";
import { colourSurfaces, type SurfaceId } from "../../../lib/colourSurfaces";
import type { Theme } from "../../../lib/colourFix";
import { SurfaceSection } from "./SurfaceSection";

type Choice = SurfaceId | "all";
const ORDER: SurfaceId[] = ["member", "public", "printed", "screens", "staff"];

/** One audience's previews at a time; "All" stacks them. Arrow keys move between tabs. */
export function AudienceTabs({ theme }: { theme: Theme }) {
  const [choice, setChoice] = useState<Choice>("member");
  const surfaces = ORDER.map((id) => colourSurfaces().find((surface) => surface.id === id)!);
  const tabs: [Choice, string][] = [...surfaces.map((s): [Choice, string] => [s.id, s.title]), ["all", t`All`]];
  const move = (event: KeyboardEvent, index: number) => {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const next = tabs[(index + step + tabs.length) % tabs.length][0];
    setChoice(next);
    document.getElementById(`audience-tab-${next}`)?.focus();
  };
  return <div className="grid min-w-0 content-start gap-3">
    <div role="tablist" aria-label={t`Who sees it`} className="flex flex-wrap items-start gap-2">
      {tabs.map(([key, label], index) => <button key={key} id={`audience-tab-${key}`} type="button" role="tab" aria-selected={choice === key}
        aria-controls="audience-panel" tabIndex={choice === key ? 0 : -1} onKeyDown={(event) => move(event, index)} onClick={() => setChoice(key)}
        className={choice === key ? "desk-button-primary" : "desk-button"}>{label}</button>)}
    </div>
    <div id="audience-panel" role="tabpanel" aria-labelledby={`audience-tab-${choice}`} className="grid min-w-0 content-start gap-3">
      {surfaces.filter((surface) => choice === "all" || surface.id === choice).map((surface) => <SurfaceSection key={surface.id} surface={surface} theme={theme} />)}
    </div>
  </div>;
}
