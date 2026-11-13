import { t } from "@lingui/core/macro";
import { useState, type DragEvent } from "react";
import { ArrowDown, ArrowUp, EyeOff, GripVertical, Pencil } from "lucide-react";
import { StatusBadge, StatusPill } from "../../../components/ui";
import type { CrewKind, CrewRow } from "./api";

export const CREW_KINDS: CrewKind[] = ["organiser", "volunteer", "mentor", "judge"];
export const crewKindLabel = (kind: CrewKind) =>
  ({ organiser: t`Organiser`, volunteer: t`Volunteer`, mentor: t`Mentor`, judge: t`Judge` })[kind];

type Edit = { crew_role: string; kind: CrewKind | ""; staff_hidden: boolean };
export type CrewRowProps = {
  row: CrewRow; kinds: boolean; pending: boolean;
  onDecide: (approve: boolean) => void; onRemove: () => void; onSave: (changes: Record<string, unknown>) => void;
  /** Reordering is offered for approved crew only (the server orders by state first). */
  reorder?: { index: number; count: number; move: (to: number) => void; drag: { onDragStart: (e: DragEvent) => void; onDragOver: (e: DragEvent) => void; onDrop: (e: DragEvent) => void; onDragEnd: () => void }; dragging: boolean };
};

/** One crew member: kind chip, hidden flag, review buttons, the staff edit form and the reorder handles (C8). */
export function CrewRowCard({ row, kinds, pending, onDecide, onRemove, onSave, reorder }: CrewRowProps) {
  const [edit, setEdit] = useState<Edit | null>(null);
  const start = () => setEdit({ crew_role: row.crew_role ?? "", kind: row.kind ?? "", staff_hidden: !!row.staff_hidden });
  const save = () => {
    if (!edit) return;
    onSave({ crew_role: edit.crew_role.trim(), staff_hidden: edit.staff_hidden, ...(kinds ? { kind: edit.kind || null } : {}) });
    setEdit(null);
  };
  return <li draggable={!!reorder && !edit} {...(reorder && !edit ? reorder.drag : {})}
    className={`rounded-xl border bg-panel p-4 transition-opacity ${reorder?.dragging ? "border-outline opacity-60" : "border-line"}`}>
    <div className="flex flex-wrap items-center gap-3">
      {reorder ? <span className="cursor-grab text-muted active:cursor-grabbing" title={t`Drag to reorder`}><GripVertical aria-hidden="true" className="size-4" /></span> : null}
      <div className="min-w-0 flex-1">
        <p className="truncate font-semibold text-ink">{row.name}</p>
        <div className="mt-1 flex flex-wrap items-center gap-1.5 text-sm text-muted">
          <span>{row.crew_role || t`Crew`}{row.has_place ? t` · crew place` : ""}</span>
          {kinds && row.kind ? <StatusPill tone="info" icon="User" label={crewKindLabel(row.kind)} /> : null}
          {row.staff_hidden ? <span className="inline-flex items-center gap-1 rounded-full border border-line px-2 py-0.5 text-xs font-semibold">
            <EyeOff aria-hidden="true" className="size-3" />{t`Hidden from the public page`}</span> : null}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={row.state} label={row.state === "applied" ? t`Waiting for review` : t`On the crew`} />
        {reorder ? <>
          <button type="button" className="desk-button min-h-11 min-w-11" aria-label={t`Move ${row.name} up`} disabled={pending || reorder.index === 0}
            onClick={() => reorder.move(reorder.index - 1)}><ArrowUp aria-hidden="true" className="size-4" /></button>
          <button type="button" className="desk-button min-h-11 min-w-11" aria-label={t`Move ${row.name} down`} disabled={pending || reorder.index === reorder.count - 1}
            onClick={() => reorder.move(reorder.index + 1)}><ArrowDown aria-hidden="true" className="size-4" /></button></> : null}
        {!edit ? <button type="button" className="desk-button inline-flex min-h-11 items-center gap-2" disabled={pending} onClick={start}>
          <Pencil aria-hidden="true" className="size-4" />{t`Edit`}</button> : null}
        {row.state === "applied" ? <>
          <button type="button" className="desk-button min-h-11" disabled={pending} onClick={() => onDecide(true)}>{t`Approve`}</button>
          <button type="button" className="desk-button min-h-11" disabled={pending} onClick={() => onDecide(false)}>{t`Decline`}</button>
        </> : <button type="button" className="desk-button min-h-11" disabled={pending} onClick={onRemove}>{t`Remove`}</button>}
      </div>
    </div>
    {edit ? <form className="mt-3 grid gap-3 border-t border-line pt-3 sm:grid-cols-2" onSubmit={event => { event.preventDefault(); save(); }}
      aria-label={t`Edit ${row.name}`}>
      <label className="grid gap-1 text-sm font-semibold text-ink">{t`Role`}
        <input className="desk-input min-h-11" maxLength={60} value={edit.crew_role} placeholder={t`Door, AV, mentor`}
          onChange={e => setEdit({ ...edit, crew_role: e.target.value })} /></label>
      {kinds ? <label className="grid gap-1 text-sm font-semibold text-ink">{t`Kind`}
        <select className="desk-input min-h-11" value={edit.kind} onChange={e => setEdit({ ...edit, kind: e.target.value as Edit["kind"] })}>
          <option value="">{t`No kind`}</option>{CREW_KINDS.map(kind => <option key={kind} value={kind}>{crewKindLabel(kind)}</option>)}</select></label> : null}
      <label className="flex min-h-11 items-start gap-3 text-sm text-ink sm:col-span-2">
        <input type="checkbox" className="mt-1" checked={edit.staff_hidden} onChange={e => setEdit({ ...edit, staff_hidden: e.target.checked })} />
        <span>{t`Hide from the public crew section`}<span className="block text-xs text-muted">{t`They stay on the crew and keep their place; only the event page leaves them out.`}</span></span></label>
      <div className="flex flex-wrap gap-2 sm:col-span-2">
        <button type="submit" className="desk-button-primary min-h-11" disabled={pending}>{t`Save changes`}</button>
        <button type="button" className="desk-button min-h-11" onClick={() => setEdit(null)}>{t`Cancel`}</button></div>
    </form> : null}
  </li>;
}
