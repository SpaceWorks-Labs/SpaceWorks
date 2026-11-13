// The studio's frame: the left icon rail (one panel at a time) and the compact canvas bar (side, two-sided,
// black and white, grid, snap) that sits above the card.
import { t } from "@lingui/core/macro";
import { History, Images, LayoutTemplate, Layers, ListChecks, PaintBucket, Plus, Ruler, type LucideIcon } from "lucide-react";

import { GRID_SIZES_MM } from "./cardGeometry";
import type { CardDocument, SideName } from "./cardTypes";
import type { Panel } from "./DesignerSidePanel";
import type { ViewOptions } from "./DesignToolbar";
import { rove } from "../ui/useRovingFocus";

export type RailKey = Panel | "templates";
const items = (): { key: RailKey; label: string; icon: LucideIcon }[] => [
  { key: "add", label: t`Add`, icon: Plus }, { key: "layers", label: t`Layers`, icon: Layers },
  { key: "background", label: t`Background`, icon: PaintBucket }, { key: "library", label: t`Library`, icon: Images },
  { key: "templates", label: t`Templates`, icon: LayoutTemplate },
  { key: "guides", label: t`Page`, icon: Ruler }, { key: "checks", label: t`Checks`, icon: ListChecks }, { key: "history", label: t`History`, icon: History },
];

export function StudioRail({ panel, onPanel, onTemplates, flagged, noHistory }: {
  panel: Panel; onPanel: (panel: Panel) => void; onTemplates: () => void; flagged: number;
  /** A certificate draft: no revision history and no space artwork library here (its artwork is the event's). */ noHistory?: boolean;
}) {
  return <nav aria-label={t`Tools`} className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible" onKeyDown={(event) => rove(event, "button", false)}>
    {items().filter((item) => !(noHistory && (item.key === "history" || item.key === "library"))).map(({ key, label, icon: Icon }) => {
      const active = key === panel;
      return <button key={key} type="button" aria-pressed={key === "templates" ? undefined : active}
        aria-label={key === "checks" && flagged ? t`${label}, ${flagged} to look at` : label} title={label}
        onClick={() => (key === "templates" ? onTemplates() : onPanel(key))}
        className={`relative grid min-h-14 min-w-14 flex-1 place-items-center gap-0.5 rounded-control border px-1 py-1.5 text-[11px] font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus lg:flex-none ${active ? "border-accent-ink bg-accent-soft text-ink" : "border-transparent text-muted hover:bg-hover hover:text-ink"}`}>
        <Icon size={20} aria-hidden="true" />
        <span className="leading-tight">{label}</span>
        {key === "checks" && flagged ? <span aria-hidden="true" className="absolute right-1 top-1 min-w-4 rounded-full bg-warn px-1 text-[10px] leading-4 text-on-warn">{flagged}</span> : null}
      </button>;
    })}
  </nav>;
}

const chip = (on: boolean) => `min-h-11 rounded-control px-3 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-focus ${on ? "bg-panel text-ink shadow-sm" : "text-muted hover:text-ink"} disabled:opacity-40`;
const check = "flex min-h-11 items-center gap-2 text-sm text-ink";

export function CanvasBar({ document, view, onView, onDocument, canEdit }: {
  document: CardDocument; view: ViewOptions; onView: (view: ViewOptions) => void; canEdit: boolean;
  onDocument: (change: (current: CardDocument) => CardDocument) => void;
}) {
  const certificate = document.kind === "certificate";
  return <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
    {certificate ? null : <div role="radiogroup" aria-label={t`Side`} className="inline-flex gap-1 rounded-control border border-line bg-surface p-1">
      {(["front", "back"] as const).map((side) => <button key={side} type="button" role="radio" aria-checked={view.side === side}
        disabled={side === "back" && !document.back_enabled} className={chip(view.side === side)}
        onClick={() => onView({ ...view, side })}>{side === "front" ? t`Front` : t`Back`}</button>)}
    </div>}
    {certificate ? null : <label className={check}>
      <input type="checkbox" className="h-5 w-5 accent-[rgb(var(--color-accent-ink))]" checked={document.back_enabled} disabled={!canEdit}
        onChange={(event) => { const back_enabled = event.target.checked; onDocument((current) => ({ ...current, back_enabled })); if (!back_enabled) onView({ ...view, side: "front" }); }} />
      {t`Two-sided`}</label>}
    <label className={check}>
      <input type="checkbox" className="h-5 w-5 accent-[rgb(var(--color-accent-ink))]" checked={document.mono} disabled={!canEdit}
        onChange={(event) => { const mono = event.target.checked; onDocument((current) => ({ ...current, mono })); }} />
      {t`Black and white`}</label>
    <label className={check}>
      <input type="checkbox" className="h-5 w-5 accent-[rgb(var(--color-accent-ink))]" checked={view.showGrid}
        onChange={(event) => onView({ ...view, showGrid: event.target.checked })} />
      {t`Grid`}</label>
    <label className={check}>
      <input type="checkbox" className="h-5 w-5 accent-[rgb(var(--color-accent-ink))]" checked={Boolean(view.showRulers)}
        onChange={(event) => onView({ ...view, showRulers: event.target.checked })} />
      {t`Rulers`}</label>
    <label className="flex min-h-11 items-center gap-2 text-sm text-ink">{t`Snap`}
      <select className="desk-input min-h-11" value={view.gridMm} onChange={(event) => onView({ ...view, gridMm: Number(event.target.value) })}>
        {GRID_SIZES_MM.map((size) => <option key={size} value={size}>{`${size} mm`}</option>)}
      </select></label>
  </div>;
}

export type { SideName };
