import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState, StatusPill } from "../../../components/ui";
import { MembershipPagination } from "../../staff/MembershipPagination";
import { useDebouncedValue } from "../../../lib/useDebouncedValue";
import { MembershipReasonDialog } from "../../staff/MembershipReasonDialog";
import { guestErrorText, guestKeys, guestStaffApi, type StaffPass } from "../api";
import {
  entitlementSummary, passKindLabel, passStatusLabel, passStatusTone, passWindow, paymentStatusLabel,
} from "../labels";
import { GuestPassIssueDialog } from "./GuestPassIssueDialog";
import { GuestPassScan } from "./GuestPassScan";
import { LogoLoader } from "../../../components/LogoLoader";
import { BoxArt } from "../../../components/BoxSpinner";
import { SearchField } from "../../../components/ui/SearchField";

const STATUSES = ["", "issued", "active", "expired", "revoked", "converted"];
const KINDS = ["", "event", "sponsored", "day"];

/**
 * Members › Guests (decision 223): the space's guest passes. manage_members on the server;
 * this section exists only while `membership.guest_passes` is on (`communityMemberTabs`).
 */
export function GuestPassDesk({ makerspaceId, dayPassesOn }: { makerspaceId: number; dayPassesOn: boolean }) {
  const client = useQueryClient();
  const [status, setStatus] = useState("");
  const [kind, setKind] = useState("");
  const [page, setPage] = useState(1);
  const [dialog, setDialog] = useState<"issue" | "sell" | null>(null);
  const [revoking, setRevoking] = useState<StaffPass | null>(null);
  // PE5: find a pass by its guest's or sponsor's name (the server's `q`).
  const [search, setSearch] = useState("");
  const q = useDebouncedValue(search.trim());
  const filters = { status, kind, ...(q ? { q } : {}), page: String(page) };
  const roster = useQuery({ queryKey: guestKeys.roster(makerspaceId, filters), queryFn: () => guestStaffApi.roster(makerspaceId, filters) });
  const refresh = () => client.invalidateQueries({ queryKey: guestKeys.all(makerspaceId) });
  const stamp = useMutation({ mutationFn: (passId: number) => guestStaffApi.stampWaiver(makerspaceId, passId), onSuccess: refresh });
  const revoke = useMutation({
    mutationFn: ({ passId, reason }: { passId: number; reason: string }) => guestStaffApi.revoke(makerspaceId, passId, reason),
    onSuccess: () => { setRevoking(null); void refresh(); void client.invalidateQueries({ queryKey: ["payments", makerspaceId] }); },
  });
  const rows = roster.data?.results ?? [];
  const pick = (setter: (value: string) => void) => (value: string) => { setter(value); setPage(1); };
  return <section aria-label={t`Guest passes`} className="grid gap-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="max-w-prose text-sm text-muted">{t`Guests visit on a dated pass: invited by a member, issued for an event, or bought for a day. Passes are not memberships and are not counted as members.`}</p>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button-primary min-h-11" onClick={() => setDialog("issue")}>{t`Issue a pass`}</button>
        {dayPassesOn ? <button type="button" className="desk-button min-h-11" onClick={() => setDialog("sell")}>{t`Sell a day pass`}</button> : null}
      </div>
    </div>
    <GuestPassScan makerspaceId={makerspaceId} />
    <div className="flex flex-wrap gap-3">
      <label className="grid min-w-0 gap-1 text-xs text-muted">{t`Guest or sponsor`}
        <SearchField className="desk-input min-h-11" value={search} onChange={(event) => pick(setSearch)(event.target.value)} /></label>
      <label className="grid gap-1 text-xs text-muted">{t`Status`}
        <select className="desk-input min-h-11" value={status} onChange={(event) => pick(setStatus)(event.target.value)}>
          {STATUSES.map((value) => <option key={value} value={value}>{value ? passStatusLabel(value) : t`All`}</option>)}</select></label>
      <label className="grid gap-1 text-xs text-muted">{t`Kind`}
        <select className="desk-input min-h-11" value={kind} onChange={(event) => pick(setKind)(event.target.value)}>
          {KINDS.map((value) => <option key={value} value={value}>{value ? passKindLabel(value) : t`All`}</option>)}</select></label>
    </div>
    {roster.isLoading ? <LogoLoader label={t`Loading guest passes…`} size={48} className="min-h-16 py-3" /> : null}
    {roster.isError ? <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-danger"><p>{guestErrorText(roster.error)}</p>
      <button type="button" className="desk-button" onClick={() => void roster.refetch()}>{t`Try again`}</button></div> : null}
    {roster.isSuccess && !rows.length ? <EmptyState message={status || kind || q ? t`No passes match these filters.` : t`No guest passes yet. Issue one, or let members bring guests.`} /> : null}
    <ul className="grid gap-3">
      {rows.map((row) => <GuestPassRow key={row.id} row={row} stamping={stamp.isPending && stamp.variables === row.id}
        onStamp={() => stamp.mutate(row.id)} onRevoke={() => { revoke.reset(); setRevoking(row); }} />)}
    </ul>
    {stamp.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(stamp.error)}</p> : null}
    <MembershipPagination label={t`guest passes`} page={page} next={roster.data?.next} previous={roster.data?.previous} fetching={roster.isFetching} onPage={setPage} />
    {dialog ? <GuestPassIssueDialog makerspaceId={makerspaceId} mode={dialog} onClose={() => setDialog(null)} /> : null}
    {revoking ? <MembershipReasonDialog title={t`Withdraw ${revoking.holder_name || revoking.holder_email}'s pass`} pending={revoke.isPending}
      error={revoke.error ? guestErrorText(revoke.error) : null} onClose={() => setRevoking(null)}
      onConfirm={(reason) => revoke.mutate({ passId: revoking.id, reason })} /> : null}
  </section>;
}

function GuestPassRow({ row, stamping, onStamp, onRevoke }: { row: StaffPass; stamping: boolean; onStamp: () => void; onRevoke: () => void }) {
  const live = row.status === "active" || row.status === "issued";
  const payment = paymentStatusLabel(row.payment_status);
  return <li className="flex min-w-0 flex-wrap items-start gap-3 rounded-2xl border border-line bg-panel p-4">
    <div className="min-w-0 flex-1 basis-56">
      <p className="title-section break-words">{row.holder_name || row.holder_email}</p>
      <p className="text-sm text-muted [overflow-wrap:anywhere]">{row.holder_email}{row.sponsor_name ? ` · ${t`Guest of ${row.sponsor_name}`}` : ""}</p>
      <p className="mt-1 text-sm text-muted">{passWindow(row.valid_from, row.valid_until)} · {entitlementSummary(row.entitlements)}</p>
      {row.revoked_reason ? <p className="mt-1 text-sm text-muted">{t`Reason: ${row.revoked_reason}`}</p> : null}
    </div>
    <div className="flex flex-wrap items-center gap-2">
      <StatusPill label={passKindLabel(row.kind)} />
      <StatusPill tone={passStatusTone(row.status)} label={passStatusLabel(row.status)} />
      {payment ? <StatusPill tone={row.payment_status === "pending" ? "warn" : "neutral"} label={payment} /> : null}
      {row.waiver_accepted_at ? <StatusPill tone="success" label={t`Waiver accepted`} />
        : live ? <button type="button" className="desk-button min-h-11" disabled={stamping} onClick={onStamp}>{stamping ? <><BoxArt size={16} mono />{t`Recording…`}</> : t`Waiver accepted at the desk`}</button> : null}
      {live ? <button type="button" className="desk-button-ghost min-h-11" onClick={onRevoke}>{t`Withdraw pass`}</button> : null}
    </div>
  </li>;
}
