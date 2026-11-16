import { t } from "@lingui/core/macro";
import { useState } from "react";
import type { SavedView } from "./SavedViewsMenu";

/** One of the viewer's own saved views in "Manage views": rename, copy its link, share, delete (B25). */
export function SavedViewRow({ view, canShare, pending, onRename, onShare, onDelete, onCopy }: {
  view: SavedView; canShare: boolean; pending: boolean;
  onRename: (name: string) => void; onShare: () => void; onDelete: () => void; onCopy: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(view.name);
  return <div className="grid gap-2 border-b border-line pb-3">
    {editing ? <form className="flex flex-wrap items-end gap-2" onSubmit={event => { event.preventDefault(); if (name.trim()) { onRename(name.trim()); setEditing(false); } }}>
      <label className="grid min-w-0 flex-1 gap-1 text-sm">{t`New name for ${view.name}`}
        <input className="desk-input" maxLength={80} required autoFocus value={name} onChange={event => setName(event.target.value)} /></label>
      <button type="submit" className="desk-button-primary" disabled={pending || !name.trim() || name.trim() === view.name}>{t`Save name`}</button>
      <button type="button" className="desk-button" onClick={() => { setName(view.name); setEditing(false); }}>{t`Cancel`}</button>
    </form> : <span className="font-semibold">{view.name}</span>}
    <div className="flex flex-wrap gap-2">
      {!editing ? <button type="button" className="desk-button" disabled={pending} onClick={() => setEditing(true)}>{t`Rename ${view.name}`}</button> : null}
      <button type="button" className="desk-button" onClick={onCopy}>{t`Copy link to ${view.name}`}</button>
      {canShare ? <button type="button" className="desk-button" disabled={pending} onClick={onShare}>{view.shared ? t`Make private` : t`Share to makerspace`}</button> : null}
      <button type="button" className="desk-button-ghost text-danger" disabled={pending} onClick={onDelete}>{t`Delete ${view.name}`}</button>
    </div>
  </div>;
}
