// The staff ID card register: every active staff member with their card state. Search, a card filter,
// issue one or many (with a summary of anyone skipped), the "roles changed" badge with one-click reissue,
// and the per-card actions. A bulk print sheet of the ticked live cards queues a server job.
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Badge, DataTable, ErrorBlock, FilterBar, OverflowMenu, SegmentedControl, type DataTableColumn } from "../../../../components/ui";
import { toast } from "../../../../components/ui/toastStore";
import { useStartCardJob } from "../../../cards/cardJobs";
import { useBulkIssueStaffCards, useIssueStaffCard, useStaffCards, staffCardJobsPath } from "./api";
import { BulkIssueSummary } from "./BulkIssueSummary";
import { useStaffCardActions } from "./StaffCardActions";
import type { BulkIssueResult, StaffCardFilter, StaffCardHolder } from "./types";

export function StaffCardsList({ makerspaceId, deskPrint }: { makerspaceId: number; deskPrint: boolean }) {
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<StaffCardFilter>("all");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number[]>([]);
  const [summary, setSummary] = useState<BulkIssueResult | null>(null);
  const list = useStaffCards(makerspaceId, q, filter, page);
  const issue = useIssueStaffCard(makerspaceId);
  const bulk = useBulkIssueStaffCards(makerspaceId);
  const job = useStartCardJob(staffCardJobsPath(makerspaceId));
  const row = useStaffCardActions(makerspaceId, deskPrint);
  const rows = list.data?.results ?? [];
  const chosen = rows.filter((holder) => selected.includes(holder.membership_id));
  const liveIds = chosen.filter((holder) => holder.card?.status === "valid").map((holder) => holder.card!.id);
  const issuable = chosen.filter((holder) => holder.card?.status !== "valid").map((holder) => holder.membership_id);

  const columns: DataTableColumn<StaffCardHolder>[] = [
    { key: "name", header: t`Name`, phone: "title", render: (holder) => <span className="grid"><span className="font-medium text-ink">{holder.name}</span>
      {holder.machine_scope ? <span className="text-xs text-muted">{holder.machine_scope}</span> : null}</span> },
    { key: "roles_text", header: t`Roles`, phone: "detail", render: (holder) => <span className="text-sm">{holder.roles_text || "—"}</span> },
    { key: "number", header: t`Card`, phone: "detail", render: (holder) => <span className="tabular-nums text-xs">{holder.card?.number ?? "—"}</span> },
    { key: "status", header: t`Status`, phone: "status", render: (holder) => <StatusCell holder={holder} onReissue={row.reissue} busy={row.reissuing} /> },
    { key: "actions", header: t`Actions`, render: (holder) => <div className="desk-actions flex flex-wrap items-center gap-2">
      {holder.card?.status !== "valid" ? <button type="button" className="desk-button min-h-11" disabled={!holder.eligible || issue.isPending}
        title={holder.eligible ? undefined : t`This account is disabled or restricted.`}
        onClick={() => issue.mutate(holder.membership_id, { onSuccess: () => toast(t`Card issued to ${holder.name}.`, { tone: "success" }) })}>
        {holder.card ? t`Issue a new card` : t`Issue card`}</button> : null}
      {holder.card?.status === "valid" ? <OverflowMenu label={t`Actions for ${holder.name}`} actions={row.actions(holder)} /> : null}
    </div> },
  ];

  return <section className="grid gap-3" aria-label={t`Staff ID cards`}>
    <FilterBar value={q} onChange={(value) => { setQ(value); setPage(1); }} placeholder={t`Search staff by name`} searchLabel={t`Search staff`}
      actions={<>
        <button type="button" className="desk-button min-h-11" disabled={!issuable.length || bulk.isPending}
          onClick={() => bulk.mutate(issuable, { onSuccess: (result) => { setSummary(result); setSelected([]); } })}>
          {bulk.isPending ? t`Issuing…` : t`Issue to ${issuable.length} selected`}</button>
        <button type="button" className="desk-button-ghost min-h-11" disabled={!liveIds.length || job.isPending}
          onClick={() => job.mutate({ kind: "bulk_sheet", card_ids: liveIds }, { onSuccess: () => toast(t`Print sheet queued. Find it under Print jobs.`, { tone: "success" }) })}>
          {t`Print sheet of ${liveIds.length} selected`}</button>
      </>}>
      <SegmentedControl label={t`Card state`} value={filter} onChange={(value) => { setFilter(value as StaffCardFilter); setPage(1); setSelected([]); }}
        options={[{ value: "all", label: t`All staff` }, { value: "none", label: t`No card` }, { value: "live", label: t`Has a card` }]} />
    </FilterBar>
    {summary ? <BulkIssueSummary result={summary} names={rows} onDismiss={() => setSummary(null)} /> : null}
    {list.isError ? <ErrorBlock error={list.error} resource={t`staff cards`} onRetry={() => void list.refetch()} /> : null}
    {issue.error || bulk.error || job.error ? <ErrorBlock error={issue.error ?? bulk.error ?? job.error} /> : null}
    <DataTable columns={columns} data={rows} loading={list.isLoading} getRowId={(holder) => holder.membership_id}
      selectedIds={selected} onSelectionChange={(ids) => setSelected(ids.map(Number))} caption={t`Staff and their ID cards`}
      emptyTitle={t`No staff found`} emptyDescription={t`Staff appear here once they hold a role in this space.`} />
    {list.data && (list.data.next || list.data.previous) ? <div className="flex items-center justify-between gap-2">
      <button type="button" className="desk-button-ghost min-h-11" disabled={!list.data.previous} onClick={() => setPage(page - 1)}>{t`Previous`}</button>
      <span className="text-sm text-muted">{t`Page ${page}`}</span>
      <button type="button" className="desk-button-ghost min-h-11" disabled={!list.data.next} onClick={() => setPage(page + 1)}>{t`Next`}</button>
    </div> : null}
    {row.dialogs}
  </section>;
}

function StatusCell({ holder, onReissue, busy }: { holder: StaffCardHolder; onReissue: (holder: StaffCardHolder) => void; busy: boolean }) {
  const card = holder.card;
  if (!card) return <Badge tone="neutral">{t`No card`}</Badge>;
  if (card.status === "revoked") return <span className="flex flex-wrap items-center gap-2"><Badge tone="danger">{t`Revoked`}</Badge>
    {card.revoked_reason ? <span className="text-xs text-muted">{card.revoked_reason}</span> : null}</span>;
  return <span className="flex flex-wrap items-center gap-2"><Badge tone="success">{t`Valid`}</Badge>
    {card.roles_changed_since_issue ? <>
      <Badge tone="warn">{t`Roles changed since issue`}</Badge>
      <button type="button" className="desk-button-ghost min-h-11" disabled={busy} onClick={() => onReissue(holder)}>{t`Reissue`}</button>
    </> : null}</span>;
}
