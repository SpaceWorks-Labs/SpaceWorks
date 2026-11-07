// The designer's tool panel: Add · Layers · Background · Checks · History.
import { t } from "@lingui/core/macro";
import { History, Layers, ListChecks, PaintBucket, Plus, type LucideIcon } from "lucide-react";

import { rove } from "../ui/useRovingFocus";
import type { CardDesign, CardDocument, SideName } from "./cardTypes";
import { AddLayerMenu } from "./AddLayerMenu";
import { BackgroundPicker, WatermarkPicker } from "./BackgroundPicker";
import { withSide } from "./designDocument";
import { HistoryPanel } from "./HistoryPanel";
import { LayerList, type PickModifiers } from "./LayerList";
import type { Issue } from "./preflight";
import { PreflightPanel } from "./PreflightPanel";
import type { DesignerEditing } from "./useDesignerEditing";

export type Panel = "add" | "layers" | "background" | "checks" | "history";

const PANELS: { value: Panel; label: string; icon: LucideIcon }[] = [
  { value: "add", label: t`Add`, icon: Plus }, { value: "layers", label: t`Layers`, icon: Layers },
  { value: "background", label: t`Background`, icon: PaintBucket }, { value: "checks", label: t`Checks`, icon: ListChecks },
  { value: "history", label: t`History`, icon: History },
];

function PanelTabs({ value, onChange, flagged }: { value: Panel; onChange: (panel: Panel) => void; flagged: number }) {
  return <div role="radiogroup" aria-label={t`Tools`} className="grid grid-cols-5 gap-1 rounded-control border border-line bg-surface p-1"
    onKeyDown={(event) => rove(event, '[role="radio"]', true)}>
    {PANELS.map(({ value: key, label, icon: Icon }) => <button key={key} type="button" role="radio" aria-checked={value === key}
      tabIndex={value === key ? 0 : -1} onClick={() => onChange(key)}
      aria-label={key === "checks" && flagged ? t`${label}, ${flagged} to look at` : label}
      className={`relative grid min-h-14 min-w-0 place-items-center gap-0.5 rounded-control border px-0.5 py-1 text-[11px] font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${value === key ? "border-outline bg-panel text-ink" : "border-transparent text-muted hover:text-ink"}`}>
      <Icon size={18} aria-hidden="true" />
      <span className="max-w-full text-center leading-tight">{key === "background" ? <>{t`Back`}<wbr />ground</> : label}</span>
      {key === "checks" && flagged ? <span aria-hidden="true"
        className="absolute right-0.5 top-0.5 min-w-4 rounded-full bg-warn px-1 text-[10px] leading-4 text-on-warn">{flagged}</span> : null}
    </button>)}
  </div>;
}

export function DesignerSidePanel({ panel, onPanel, design, document, sideName, selection, editing, onPick, onAssetColour,
  update, issues, onIssue, values, history }: {
  panel: Panel; onPanel: (panel: Panel) => void; design: CardDesign; document: CardDocument; sideName: SideName;
  selection: string[]; editing: DesignerEditing; onPick: (id: string, modifiers: PickModifiers) => void;
  onAssetColour: (assetId: string, colour: string) => void;
  update: (change: (current: CardDocument) => CardDocument) => void; issues: Issue[];
  onIssue: (side: SideName, layerId: string | null) => void; values: Record<string, string>;
  history: { prepare: () => Promise<number>; onRestored: (design: CardDesign) => void; onReload: () => void };
}) {
  const side = document[sideName];
  const readOnly = !editing.canEdit;
  const flagged = issues.filter((issue) => issue.severity !== "info").length;
  return <aside className="grid min-w-0 grid-cols-1 content-start gap-3 rounded-card border border-line bg-panel p-3" aria-label={t`Design tools`}>
    <PanelTabs value={panel} onChange={onPanel} flagged={flagged} />
    {panel === "add" ? <AddLayerMenu side={side} stock={document.stock} domain={design.domain} designId={design.id}
      answerFields={design.answer_fields}
      readOnly={readOnly} onAssetColour={onAssetColour} onAdd={editing.add} /> : null}
    {panel === "add" && readOnly ? <p className="text-sm text-muted">{t`You can view this design but not change it.`}</p> : null}
    {panel === "layers" ? <LayerList layers={side.layers} selection={selection} readOnly={readOnly} onPick={onPick}
      onPatch={editing.patchOne} onRemove={(id) => editing.remove([id])} onMove={editing.reorder}
      onDuplicate={(id) => editing.duplicate([id])} /> : null}
    {panel === "background" ? <div className="grid gap-4">
      <BackgroundPicker designId={design.id} background={side.background} readOnly={readOnly} onAssetColour={onAssetColour}
        onChange={(background) => update((current) => withSide(current, sideName, (value) => ({ ...value, background })))} />
      <WatermarkPicker designId={design.id} watermark={document.watermark} readOnly={readOnly} onAssetColour={onAssetColour}
        onChange={(watermark) => update((current) => ({ ...current, watermark }))} />
    </div> : null}
    {panel === "checks" ? <PreflightPanel issues={issues} onPick={onIssue} /> : null}
    {panel === "history" ? <HistoryPanel designId={design.id} canEdit={editing.canEdit} values={values}
      prepare={history.prepare} onRestored={history.onRestored} onReload={history.onReload} /> : null}
  </aside>;
}
