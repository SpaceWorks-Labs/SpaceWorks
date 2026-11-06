// The inspector when several layers are selected: what they share, and the actions that
// apply to all of them at once. Locked layers stay where they are.
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
  return <div className="grid gap-4" role="group" aria-label={`${layers.length} layers selected`}>
    <div className="grid gap-1">
      <h3 className="text-sm font-semibold text-ink">{layers.length} layers selected</h3>
      <p className="text-sm text-muted">
        {groups.length === 1 && layers.every((layer) => layer.group === groups[0]) ? `Group ${labels[groups[0]]}. ` : ""}
        Drag any of them to move them together. Use the bar above the card to line them up.
        {locked ? ` ${locked} locked ${locked === 1 ? "layer stays" : "layers stay"} put.` : ""}</p>
    </div>
    <ul className="grid max-h-40 gap-1 overflow-y-auto text-sm text-ink" aria-label="Selected layers">
      {layers.map((layer) => <li key={layer.id} className="truncate">
        {layerName(layer)}{layer.locked ? <span className="text-muted"> (locked)</span> : null}</li>)}
    </ul>
    {edit ? <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1">
      {groups.length && layers.every((layer) => layer.group === groups[0])
        ? <button type="button" className={action} onClick={editing.ungroup}><Ungroup size={16} aria-hidden="true" /> Ungroup</button>
        : <button type="button" className={action} onClick={editing.group}><Group size={16} aria-hidden="true" /> Group</button>}
      <button type="button" className={action} onClick={() => editing.duplicate()}><Copy size={16} aria-hidden="true" /> Duplicate</button>
      <button type="button" className={action} onClick={() => editing.copy()}>
        <ClipboardCopy size={16} aria-hidden="true" /> Copy (paste on either side)</button>
      <button type="button" className={action} onClick={() => editing.setFlag("locked", !allLocked)}>
        {allLocked ? <LockOpen size={16} aria-hidden="true" /> : <Lock size={16} aria-hidden="true" />}
        {allLocked ? "Unlock all" : "Lock all"}</button>
      <button type="button" className={action} onClick={() => editing.setFlag("hidden", !allHidden)}>
        {allHidden ? <Eye size={16} aria-hidden="true" /> : <EyeOff size={16} aria-hidden="true" />}
        {allHidden ? "Show all" : "Hide all"}</button>
      <button type="button" className={`${action} text-danger`} disabled={allLocked} onClick={() => editing.remove()}>
        <Trash2 size={16} aria-hidden="true" /> Delete{locked ? " unlocked layers" : ""}</button>
    </div> : null}
  </div>;
}
