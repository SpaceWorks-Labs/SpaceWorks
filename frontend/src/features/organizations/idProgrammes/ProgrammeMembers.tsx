// Programme members: status chips with counts, search (ID number or exact email), the table,
// a bulk bar (approve, reject, revoke, renew, email, download) and "Add a person".
import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Badge, ConfirmDialog, ErrorBlock, OverflowMenu, PagePager } from "../../../components/ui";
import { JOB_LABELS, useStartCardJob } from "../../cards/cardJobs";
import { SheetPreviewDialog } from "../../cards/SheetPreviewDialog";
import { StaffPhotoDialog } from "../../cards/StaffPhotoDialog";
import { downloadProgrammeCard, programmeJobsPath, useAddProgrammeCard, useDecide, useDeleteProgrammeCard, useProgrammeCards,
  type Programme, type ProgrammeCard, type ProgrammeCardStatus } from "./api";
import { LogoLoader } from "../../../components/LogoLoader";
import { SearchField } from "../../../components/ui/SearchField";

const STATUS: Record<ProgrammeCardStatus, { label: string; tone: "warn" | "success" | "danger" | "neutral" }> = {
  pending: { label: t`Waiting for approval`, tone: "warn" }, approved: { label: t`Approved`, tone: "success" },
  rejected: { label: t`Not approved`, tone: "neutral" }, revoked: { label: t`Revoked`, tone: "danger" },
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
  const [sheetFor, setSheetFor] = useState<number[] | null>(null);
  const client = useQueryClient();
  const cards = useProgrammeCards(programme.id, status, search.trim(), page);
  const decide = useDecide(programme.id);
  const remove = useDeleteProgrammeCard(programme.id);
  const [deleting, setDeleting] = useState<ProgrammeCard | null>(null);
  const startJob = useStartCardJob(programmeJobsPath(programme.id));
  const manage = programme.can_manage;
  const rows = cards.data?.results ?? [];
  const run = (action: string, ids: number[], why = "") => decide.mutate({ action, ids, ...(why ? { reason: why } : {}) },
    { onSuccess: () => { setSelected([]); setPendingAction(null); setReason(""); } });
  const chips: { value: "" | ProgrammeCardStatus; label: string; count: number }[] = [
    { value: "", label: t`All`, count: programme.counts.all }, { value: "pending", label: t`Waiting`, count: programme.counts.pending },
    { value: "approved", label: t`Approved`, count: programme.counts.approved }, { value: "rejected", label: t`Not approved`, count: programme.counts.rejected },
    { value: "revoked", label: t`Revoked`, count: programme.counts.revoked }];

  return <div className="grid gap-3">
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label={t`Filter by status`}>
      {chips.map((chip) => <button key={chip.value || "all"} type="button" aria-pressed={status === chip.value}
        className={`min-h-11 rounded-full border px-3 text-sm ${status === chip.value ? "border-accent-ink bg-accent-soft text-ink" : "border-line text-muted"}`}
        onClick={() => { setStatus(chip.value); setPage(1); setSelected([]); }}>{chip.label} <span className="tabular-nums">{chip.count}</span></button>)}
      <SearchField className="desk-input min-h-11 min-w-48 flex-1" aria-label={t`Search by ID number or exact email`}
        placeholder={t`ID number or exact email`} value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} />
    </div>
    {manage ? <AddPerson programmeId={programme.id} /> : null}
    {manage && !selected.length && programme.counts.approved ? <div>
      <button type="button" className="desk-button min-h-11" onClick={() => setSheetFor([])}>{t`Print sheet of all approved cards…`}</button>
    </div> : null}
    {manage && selected.length ? <div className="flex flex-wrap items-center gap-2 rounded-control border border-line bg-surface p-2 text-sm" role="region" aria-label={t`Selected cards`}>
      <span className="font-semibold text-ink">{t`${selected.length} selected`}</span>
      {["approve", "reject", "revoke", "renew"].map((action) => <button key={action} type="button" className="desk-button min-h-11"
        disabled={decide.isPending} onClick={() => (NEEDS_REASON.has(action) ? setPendingAction(action) : run(action, selected))}>
        {action === "approve" ? t`Approve` : action === "reject" ? t`Reject…` : action === "revoke" ? t`Revoke…` : t`Renew`}</button>)}
      <button type="button" className="desk-button-ghost min-h-11" onClick={() => startJob.mutate({ kind: "email", card_ids: selected })}>{t`Email`}</button>
      <button type="button" className="desk-button-ghost min-h-11" onClick={() => startJob.mutate({ kind: "zip", card_ids: selected })}>{JOB_LABELS.zip}</button>
      <button type="button" className="desk-button-ghost min-h-11" onClick={() => setSheetFor(selected)}>{t`Print sheet…`}</button>
      <button type="button" className="desk-button-ghost min-h-11" onClick={() => setSelected([])}>{t`Clear`}</button>
    </div> : null}
    {pendingAction ? <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); run(pendingAction, selected, reason.trim()); }}>
      <label className="grid flex-1 gap-1 text-xs font-semibold text-muted"><span>{t`Reason (staff only)`}</span>
        <input className="desk-input min-h-11" value={reason} maxLength={300} onChange={(event) => setReason(event.target.value)} /></label>
      <button type="submit" className="desk-button-danger min-h-11" disabled={decide.isPending || reason.trim().length < 3}>
        {pendingAction === "reject" ? t`Reject` : t`Revoke`} {selected.length}</button>
      <button type="button" className="desk-button min-h-11" onClick={() => setPendingAction(null)}>{t`Cancel`}</button>
    </form> : null}
    {decide.error || startJob.error || remove.error ? <ErrorBlock error={decide.error ?? startJob.error ?? remove.error} /> : null}
    {cards.isError ? <ErrorBlock error={cards.error} resource={t`programme cards`} onRetry={() => void cards.refetch()} /> : null}
    <div className="overflow-x-auto rounded-card border border-line">
      <table className="w-full text-left text-sm">
        <thead className="bg-surface text-xs text-muted"><tr>
          {manage ? <th className="p-2"><span className="sr-only">{t`Select`}</span></th> : null}
          <th className="p-2">{t`Name`}</th><th className="p-2">{t`ID number`}</th><th className="p-2">{t`Status`}</th><th className="p-2">{t`Valid until`}</th>
          <th className="p-2"><span className="sr-only">{t`Actions`}</span></th></tr></thead>
        <tbody>
          {cards.isLoading ? <tr><td className="p-3 text-muted" colSpan={6}><LogoLoader size={48} className="min-h-16 py-3" /></td></tr> : null}
          {!cards.isLoading && !rows.length ? <tr><td className="p-3 text-muted" colSpan={6}>{t`No one here yet.`}</td></tr> : null}
          {rows.map((card) => <MemberRow key={card.id} card={card} manage={manage} selected={selected.includes(card.id)}
            onToggle={(on) => setSelected((current) => on ? [...current, card.id] : current.filter((id) => id !== card.id))}
            onPhoto={() => setPhotoFor(card)}
            onAction={(action) => (action === "delete" ? setDeleting(card) : NEEDS_REASON.has(action)
              ? (setSelected([card.id]), setPendingAction(action)) : run(action, [card.id]))} />)}
        </tbody>
      </table>
    </div>
    <SheetPreviewDialog open={sheetFor !== null} onClose={() => setSheetFor(null)} jobsPath={programmeJobsPath(programme.id)}
      previewPath={`${programmeJobsPath(programme.id)}/preview`} filter={sheetFor?.length ? { card_ids: sheetFor } : {}}
      title={sheetFor?.length ? t`Print sheet: ${sheetFor.length} selected cards` : t`Print sheet: all approved cards`} />
    <ConfirmDialog open={deleting !== null} tone="danger" pending={remove.isPending} title={t`Delete ${deleting?.name ?? ""}'s request?`}
      message={t`This card was never issued, so the request and its photo are deleted for good. Issued cards are revoked instead.`}
      confirmLabel={t`Delete`} onCancel={() => setDeleting(null)}
      onConfirm={() => { if (deleting) remove.mutate(deleting.id, { onSettled: () => setDeleting(null) }); }} />
    <StaffPhotoDialog holderName={photoFor?.name ?? null} photoPath={`/admin/id-programme-cards/${photoFor?.id}/photo`}
      onClose={() => setPhotoFor(null)} onSaved={() => { setPhotoFor(null); void client.invalidateQueries({ queryKey: ["id-programme-cards", programme.id] }); }} />
    {cards.data ? <PagePager page={page} setPage={setPage} count={cards.data.count} /> : null}
  </div>;
}

function MemberRow({ card, manage, selected, onToggle, onAction, onPhoto }: { card: ProgrammeCard; manage: boolean; selected: boolean;
  onToggle: (on: boolean) => void; onAction: (action: string) => void; onPhoto: () => void }) {
  const actions = [
    ...(card.status === "approved" ? [{ label: t`Download PDF`, onClick: () => void downloadProgrammeCard(card, "pdf") },
      { label: t`Download PNG`, onClick: () => void downloadProgrammeCard(card, "png") }] : []),
    ...(manage && card.status === "pending" ? [{ label: t`Approve`, onClick: () => onAction("approve") },
      { label: t`Reject`, confirms: true, onClick: () => onAction("reject") }] : []),
    ...(manage && card.status === "approved" ? [{ label: t`Renew`, onClick: () => onAction("renew") },
      { label: t`Revoke`, confirms: true, tone: "danger" as const, onClick: () => onAction("revoke") }] : []),
    ...(manage && card.status === "revoked" ? [{ label: t`Reinstate`, onClick: () => onAction("reinstate") }] : []),
    ...(manage && (card.status === "pending" || card.status === "approved")
      ? [{ label: card.photo_set ? t`Replace photo` : t`Take or upload photo`, confirms: true, onClick: onPhoto }] : []),
    // Decision 219(h): only a card that was never issued is deleted; an issued one is revoked.
    ...(manage && !card.id_number && !card.issued_at
      ? [{ label: t`Delete request`, confirms: true, tone: "danger" as const, onClick: () => onAction("delete") }] : []),
  ];
  return <tr className="border-t border-line">
    {manage ? <td className="p-2"><input type="checkbox" className="h-5 w-5" aria-label={t`Select ${card.name}`} checked={selected}
      onChange={(event) => onToggle(event.target.checked)} /></td> : null}
    <td className="p-2"><span className="text-ink">{card.name}</span>{!card.linked ? <span className="block text-xs text-muted">{t`Invite not accepted yet`}</span> : null}</td>
    <td className="p-2 tabular-nums">{card.id_number || "—"}</td>
    <td className="p-2"><Badge tone={STATUS[card.status].tone}>{STATUS[card.status].label}</Badge>
      {card.status_reason && (card.status === "rejected" || card.status === "revoked")
        ? <span className="block text-xs text-muted">{card.status_reason}</span> : null}</td>
    <td className="p-2 text-xs text-muted">{card.expires_at ? new Date(card.expires_at).toLocaleDateString(formatLocale()) : card.status === "approved" ? t`No end date` : "—"}</td>
    <td className="p-2">{actions.length ? <OverflowMenu label={t`Actions for ${card.name}`} actions={actions} /> : null}</td>
  </tr>;
}

function AddPerson({ programmeId }: { programmeId: number }) {
  const add = useAddProgrammeCard(programmeId);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  return <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => {
    event.preventDefault(); add.mutate({ name: name.trim(), email: email.trim() }, { onSuccess: () => { setName(""); setEmail(""); } });
  }}>
    <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Name`}</span>
      <input className="desk-input min-h-11" value={name} maxLength={120} onChange={(event) => setName(event.target.value)} /></label>
    <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Email`}</span>
      <input className="desk-input min-h-11" type="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
    <button type="submit" className="desk-button min-h-11" disabled={!name.trim() || !email.includes("@") || add.isPending}>{t`Add and invite`}</button>
    {add.error ? <div className="basis-full"><ErrorBlock error={add.error} /></div> : null}
  </form>;
}
