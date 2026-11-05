// Programme members: status chips with counts, search (ID number or exact email), the table,
// a bulk bar (approve, reject, revoke, renew, email, download) and "Add a person".
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Badge, ErrorBlock, OverflowMenu } from "../../../components/ui";
import { JOB_LABELS, useStartCardJob } from "../../cards/cardJobs";
import { StaffPhotoDialog } from "../../cards/StaffPhotoDialog";
import { downloadProgrammeCard, programmeJobsPath, useAddProgrammeCard, useDecide, useProgrammeCards,
  type Programme, type ProgrammeCard, type ProgrammeCardStatus } from "./api";

const STATUS: Record<ProgrammeCardStatus, { label: string; tone: "warn" | "success" | "danger" | "neutral" }> = {
  pending: { label: "Waiting for approval", tone: "warn" }, approved: { label: "Approved", tone: "success" },
  rejected: { label: "Not approved", tone: "neutral" }, revoked: { label: "Revoked", tone: "danger" },
};
const NEEDS_REASON = new Set(["reject", "revoke"]);

export function ProgrammeMembers({ programme }: { programme: Programme }) {
  const [status, setStatus] = useState<"" | ProgrammeCardStatus>("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number[]>([]);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [photoFor, setPhotoFor] = useState<ProgrammeCard | null>(null);
  const client = useQueryClient();
  const cards = useProgrammeCards(programme.id, status, search.trim(), page);
  const decide = useDecide(programme.id);
  const startJob = useStartCardJob(programmeJobsPath(programme.id));
  const manage = programme.can_manage;
  const rows = cards.data?.results ?? [];
  const run = (action: string, ids: number[], why = "") => decide.mutate({ action, ids, ...(why ? { reason: why } : {}) },
    { onSuccess: () => { setSelected([]); setPendingAction(null); setReason(""); } });
  const chips: { value: "" | ProgrammeCardStatus; label: string; count: number }[] = [
    { value: "", label: "All", count: programme.counts.all }, { value: "pending", label: "Waiting", count: programme.counts.pending },
    { value: "approved", label: "Approved", count: programme.counts.approved }, { value: "rejected", label: "Not approved", count: programme.counts.rejected },
    { value: "revoked", label: "Revoked", count: programme.counts.revoked }];

  return <div className="grid gap-3">
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by status">
      {chips.map((chip) => <button key={chip.value || "all"} type="button" aria-pressed={status === chip.value}
        className={`min-h-11 rounded-full border px-3 text-sm ${status === chip.value ? "border-accent-ink bg-accent-soft text-ink" : "border-line text-muted"}`}
        onClick={() => { setStatus(chip.value); setPage(1); setSelected([]); }}>{chip.label} <span className="tabular-nums">{chip.count}</span></button>)}
      <input className="desk-input min-h-11 min-w-48 flex-1" type="search" aria-label="Search by ID number or exact email"
        placeholder="ID number or exact email" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} />
    </div>
    {manage ? <AddPerson programmeId={programme.id} /> : null}
    {manage && selected.length ? <div className="flex flex-wrap items-center gap-2 rounded-control border border-line bg-surface p-2 text-sm" role="region" aria-label="Selected cards">
      <span className="font-semibold text-ink">{selected.length} selected</span>
      {["approve", "reject", "revoke", "renew"].map((action) => <button key={action} type="button" className="desk-button min-h-11"
        disabled={decide.isPending} onClick={() => (NEEDS_REASON.has(action) ? setPendingAction(action) : run(action, selected))}>
        {action === "approve" ? "Approve" : action === "reject" ? "Reject…" : action === "revoke" ? "Revoke…" : "Renew"}</button>)}
      <button type="button" className="desk-button-ghost min-h-11" onClick={() => startJob.mutate({ kind: "email", card_ids: selected })}>Email</button>
      <button type="button" className="desk-button-ghost min-h-11" onClick={() => startJob.mutate({ kind: "zip", card_ids: selected })}>{JOB_LABELS.zip}</button>
      <button type="button" className="desk-button-ghost min-h-11" onClick={() => setSelected([])}>Clear</button>
    </div> : null}
    {pendingAction ? <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); run(pendingAction, selected, reason.trim()); }}>
      <label className="grid flex-1 gap-1 text-xs font-semibold text-muted"><span>Reason (staff only)</span>
        <input className="desk-input min-h-11" value={reason} maxLength={300} onChange={(event) => setReason(event.target.value)} /></label>
      <button type="submit" className="desk-button-danger min-h-11" disabled={decide.isPending || reason.trim().length < 3}>
        {pendingAction === "reject" ? "Reject" : "Revoke"} {selected.length}</button>
      <button type="button" className="desk-button min-h-11" onClick={() => setPendingAction(null)}>Cancel</button>
    </form> : null}
    {decide.error || startJob.error ? <ErrorBlock error={decide.error ?? startJob.error} /> : null}
    {cards.isError ? <ErrorBlock error={cards.error} resource="programme cards" onRetry={() => void cards.refetch()} /> : null}
    <div className="overflow-x-auto rounded-card border border-line">
      <table className="w-full text-left text-sm">
        <thead className="bg-surface text-xs text-muted"><tr>
          {manage ? <th className="p-2"><span className="sr-only">Select</span></th> : null}
          <th className="p-2">Name</th><th className="p-2">ID number</th><th className="p-2">Status</th><th className="p-2">Valid until</th>
          <th className="p-2"><span className="sr-only">Actions</span></th></tr></thead>
        <tbody>
          {cards.isLoading ? <tr><td className="p-3 text-muted" colSpan={6}>Loading…</td></tr> : null}
          {!cards.isLoading && !rows.length ? <tr><td className="p-3 text-muted" colSpan={6}>No one here yet.</td></tr> : null}
          {rows.map((card) => <MemberRow key={card.id} card={card} manage={manage} selected={selected.includes(card.id)}
            onToggle={(on) => setSelected((current) => on ? [...current, card.id] : current.filter((id) => id !== card.id))}
            onPhoto={() => setPhotoFor(card)}
            onAction={(action) => (NEEDS_REASON.has(action) ? (setSelected([card.id]), setPendingAction(action)) : run(action, [card.id]))} />)}
        </tbody>
      </table>
    </div>
    <StaffPhotoDialog holderName={photoFor?.name ?? null} photoPath={`/admin/id-programme-cards/${photoFor?.id}/photo`}
      onClose={() => setPhotoFor(null)} onSaved={() => { setPhotoFor(null); void client.invalidateQueries({ queryKey: ["id-programme-cards", programme.id] }); }} />
    {cards.data && cards.data.count > 24 ? <div className="flex gap-2">
      <button type="button" className="desk-button min-h-11" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button>
      <button type="button" className="desk-button min-h-11" disabled={page * 24 >= cards.data.count} onClick={() => setPage(page + 1)}>Next</button>
    </div> : null}
  </div>;
}

function MemberRow({ card, manage, selected, onToggle, onAction, onPhoto }: { card: ProgrammeCard; manage: boolean; selected: boolean;
  onToggle: (on: boolean) => void; onAction: (action: string) => void; onPhoto: () => void }) {
  const actions = [
    ...(card.status === "approved" ? [{ label: "Download PDF", onClick: () => void downloadProgrammeCard(card, "pdf") },
      { label: "Download PNG", onClick: () => void downloadProgrammeCard(card, "png") }] : []),
    ...(manage && card.status === "pending" ? [{ label: "Approve", onClick: () => onAction("approve") },
      { label: "Reject", confirms: true, onClick: () => onAction("reject") }] : []),
    ...(manage && card.status === "approved" ? [{ label: "Renew", onClick: () => onAction("renew") },
      { label: "Revoke", confirms: true, tone: "danger" as const, onClick: () => onAction("revoke") }] : []),
    ...(manage && card.status === "revoked" ? [{ label: "Reinstate", onClick: () => onAction("reinstate") }] : []),
    ...(manage && (card.status === "pending" || card.status === "approved")
      ? [{ label: card.photo_set ? "Replace photo" : "Take or upload photo", confirms: true, onClick: onPhoto }] : []),
  ];
  return <tr className="border-t border-line">
    {manage ? <td className="p-2"><input type="checkbox" className="h-5 w-5" aria-label={`Select ${card.name}`} checked={selected}
      onChange={(event) => onToggle(event.target.checked)} /></td> : null}
    <td className="p-2"><span className="text-ink">{card.name}</span>{!card.linked ? <span className="block text-xs text-muted">Invite not accepted yet</span> : null}</td>
    <td className="p-2 tabular-nums">{card.id_number || "—"}</td>
    <td className="p-2"><Badge tone={STATUS[card.status].tone}>{STATUS[card.status].label}</Badge>
      {card.status_reason && (card.status === "rejected" || card.status === "revoked")
        ? <span className="block text-xs text-muted">{card.status_reason}</span> : null}</td>
    <td className="p-2 text-xs text-muted">{card.expires_at ? new Date(card.expires_at).toLocaleDateString() : card.status === "approved" ? "No end date" : "—"}</td>
    <td className="p-2">{actions.length ? <OverflowMenu label={`Actions for ${card.name}`} actions={actions} /> : null}</td>
  </tr>;
}

function AddPerson({ programmeId }: { programmeId: number }) {
  const add = useAddProgrammeCard(programmeId);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  return <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => {
    event.preventDefault(); add.mutate({ name: name.trim(), email: email.trim() }, { onSuccess: () => { setName(""); setEmail(""); } });
  }}>
    <label className="grid gap-1 text-xs font-semibold text-muted"><span>Name</span>
      <input className="desk-input min-h-11" value={name} maxLength={120} onChange={(event) => setName(event.target.value)} /></label>
    <label className="grid gap-1 text-xs font-semibold text-muted"><span>Email</span>
      <input className="desk-input min-h-11" type="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
    <button type="submit" className="desk-button min-h-11" disabled={!name.trim() || !email.includes("@") || add.isPending}>Add and invite</button>
    {add.error ? <div className="basis-full"><ErrorBlock error={add.error} /></div> : null}
  </form>;
}
