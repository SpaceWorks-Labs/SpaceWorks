// The designer's tool panel: Add · Layers · Background · Checks · History.
import { t } from "@lingui/core/macro";

import type { CardDesign, CardDocument, SideName, StudioSubject } from "./cardTypes";
import { AddLayerMenu } from "./AddLayerMenu";
import { AssetLibrary } from "./AssetLibrary";
import { BackgroundPicker, OverlayPicker, WatermarkPicker } from "./BackgroundPicker";
import { withSide } from "./designDocument";
import { GuidesPanel } from "./GuidesPanel";
import { HistoryPanel } from "./HistoryPanel";
import { LayerList, type PickModifiers } from "./LayerList";
import type { Issue } from "./preflight";
import { PreflightPanel } from "./PreflightPanel";
import type { DesignerEditing } from "./useDesignerEditing";

export type Panel = "add" | "layers" | "background" | "library" | "guides" | "checks" | "history";

const titles = (): Record<Panel, string> => ({ add: t`Add`, layers: t`Layers`, background: t`Background`, library: t`Library`,
  guides: t`Page and guides`, checks: t`Checks`, history: t`History` });

export function DesignerSidePanel({ panel, design, document, sideName, selection, editing, onPick, onAssetColour,
  update, issues, onIssue, values, history, fieldOptions }: {
  panel: Panel; design: StudioSubject; fieldOptions?: { key: string; label: string }[]; document: CardDocument; sideName: SideName;
  selection: string[]; editing: DesignerEditing; onPick: (id: string, modifiers: PickModifiers) => void;
  onAssetColour: (assetId: string, colour: string) => void;
  update: (change: (current: CardDocument) => CardDocument) => void; issues: Issue[];
  onIssue: (side: SideName, layerId: string | null) => void; values: Record<string, string>;
  /** Absent for a certificate draft, which keeps no revision history here (its revisions are the template revisions). */
  history?: { prepare: () => Promise<number>; onRestored: (design: CardDesign) => void; onReload: () => void };
}) {
  const side = document[sideName];
  const readOnly = !editing.canEdit;
  return <aside className="grid min-w-0 grid-cols-1 content-start gap-3" aria-label={t`Design tools`}>
    <h2 className="text-sm font-bold text-ink">{titles()[panel]}</h2>
    {panel === "add" ? <AddLayerMenu side={side} stock={document.stock} domain={design.domain} designId={design.id}
      answerFields={design.answer_fields} fieldOptions={fieldOptions}
      readOnly={readOnly} onAssetColour={onAssetColour} onAdd={editing.add} /> : null}
    {panel === "add" && readOnly ? <p className="text-sm text-muted">{t`You can view this design but not change it.`}</p> : null}
    {panel === "layers" ? <LayerList layers={side.layers} selection={selection} readOnly={readOnly} onPick={onPick}
      onPatch={editing.patchOne} onRemove={(id) => editing.remove([id])} onMove={editing.reorder} onMoveTo={editing.reorderTo} groups={side.groups} onGroupMeta={editing.groupMeta}
      onDuplicate={(id) => editing.duplicate([id])} /> : null}
    {panel === "background" ? <div className="grid gap-4">
      <BackgroundPicker designId={design.id} background={side.background} readOnly={readOnly} onAssetColour={onAssetColour}
        onChange={(background) => update((current) => withSide(current, sideName, (value) => ({ ...value, background })))} />
      <OverlayPicker overlay={side.overlay} readOnly={readOnly}
        onChange={(overlay) => update((current) => withSide(current, sideName, (value) => ({ ...value, overlay })))} />
      <WatermarkPicker designId={design.id} watermark={document.watermark} readOnly={readOnly} onAssetColour={onAssetColour}
        onChange={(watermark) => update((current) => ({ ...current, watermark }))} />
    </div> : null}
    {panel === "library" && design.id > 0 ? <AssetLibrary designId={design.id} side={side} stock={document.stock} readOnly={readOnly}
      onAssetColour={onAssetColour} onAdd={editing.add}
      onBackground={(background) => update((current) => withSide(current, sideName, (value) => ({ ...value, background })))} /> : null}
    {panel === "guides" ? <GuidesPanel document={document} sideName={sideName} update={update} readOnly={readOnly} /> : null}
    {panel === "checks" ? <PreflightPanel issues={issues} onPick={onIssue} /> : null}
    {panel === "history" && history ? <HistoryPanel designId={design.id} canEdit={editing.canEdit} values={values}
      prepare={history.prepare} onRestored={history.onRestored} onReload={history.onReload} /> : null}
  </aside>;
}
