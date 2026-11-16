// The inspector when several layers are selected: what they share, and the actions that
// apply to all of them at once. Locked layers stay where they are.
import { plural, t } from "@lingui/core/macro";
import { ClipboardCopy, Copy, Eye, EyeOff, Group, Lock, LockOpen, Trash2, Ungroup } from "lucide-react";

import type { Side } from "./cardTypes";
import { layerName } from "./designDocument";
import { groupLabels, selectedLayers } from "./selection";
import type { DesignerEditing } from "./useDesignerEditing";

export function SelectionInspector({ side, selection, editing }: { side: Side; selection: string[]; editing: DesignerEditing }) {
  const layers = selectedLayers(side, selection);
  const labels = groupLabels(side.layers);
  const groups = [...new Set(layers.map((layer) => layer.group).filter(Boolean))] as string[];
  const allLocked = layers.every((layer) => layer.locked);
  const allHidden = layers.every((layer) => layer.hidden);
  const locked = layers.filter((layer) => layer.locked).length;
  const edit = editing.canEdit;
  const action = "desk-button min-h-11 justify-start";
  return <div className="grid gap-4" role="group" aria-label={t`${layers.length} layers selected`}>
    <div className="grid gap-1">
      <h3 className="text-sm font-semibold text-ink">{t`${layers.length} layers selected`}</h3>
      <p className="text-sm text-muted">
        {groups.length === 1 && layers.every((layer) => layer.group === groups[0]) ? t`Group ${labels[groups[0]]}. ` : ""}
        {t`Drag any of them to move them together. Use the bar above the card to line them up.`}{locked ? ` ${plural(locked, { one: "# locked layer stays put.", other: "# locked layers stay put." })}` : ""}</p>
    </div>
    <ul className="grid max-h-40 gap-1 overflow-y-auto text-sm text-ink" aria-label={t`Selected layers`}>
      {layers.map((layer) => <li key={layer.id} className="truncate">
        {layerName(layer)}{layer.locked ? <span className="text-muted"> (locked)</span> : null}</li>)}
    </ul>
    {edit ? <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1">
      {groups.length && layers.every((layer) => layer.group === groups[0])
        ? <button type="button" className={action} onClick={editing.ungroup}><Ungroup size={16} aria-hidden="true" /> {t` Ungroup`}</button>
        : <button type="button" className={action} onClick={editing.group}><Group size={16} aria-hidden="true" /> {t` Group`}</button>}
      <button type="button" className={action} onClick={() => editing.duplicate()}><Copy size={16} aria-hidden="true" /> {t` Duplicate`}</button>
      <button type="button" className={action} onClick={() => editing.copy()}>
        <ClipboardCopy size={16} aria-hidden="true" /> {t` Copy (paste on either side)`}</button>
      <button type="button" className={action} onClick={() => editing.setFlag("locked", !allLocked)}>
        {allLocked ? <LockOpen size={16} aria-hidden="true" /> : <Lock size={16} aria-hidden="true" />}
        {allLocked ? t`Unlock all` : t`Lock all`}</button>
      <button type="button" className={action} onClick={() => editing.setFlag("hidden", !allHidden)}>
        {allHidden ? <Eye size={16} aria-hidden="true" /> : <EyeOff size={16} aria-hidden="true" />}
        {allHidden ? t`Show all` : t`Hide all`}</button>
      <button type="button" className={`${action} text-danger`} disabled={allLocked} onClick={() => editing.remove()}>
        <Trash2 size={16} aria-hidden="true" /> {t` Delete`}{locked ? t` unlocked layers` : ""}</button>
    </div> : null}
  </div>;
}
