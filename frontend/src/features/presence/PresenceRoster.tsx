import { plural, t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DataTable, IdentityChip } from "../../components/ui";
import { MembershipPagination } from "../staff/MembershipPagination";
import { DEFAULT_PRESETS, presenceApi, presenceKeys, type PresenceRosterRow } from "./api";
import { clockTime, presenceErrorText, STATUS_LABELS } from "./presenceCopy";
import { PresenceRelatedDialog } from "./PresenceRelatedDialog";
import { StaffCheckInDialog } from "./StaffCheckInDialog";

export type PresenceRosterProps = { makerspaceId: number; presets?: number[] };

/** Staff "present now" list. Scoping is server-side (manage_members through accounts.rbac);
 * staff check-in needs no location — that is the documented alternative to the geofence. */
export function PresenceRoster({ makerspaceId, presets = DEFAULT_PRESETS }: PresenceRosterProps) {
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [checkInOpen, setCheckInOpen] = useState(false);
  const [related, setRelated] = useState<PresenceRosterRow | null>(null);
  const roster = useQuery({ queryKey: presenceKeys.roster(makerspaceId, page), queryFn: () => presenceApi.roster(makerspaceId, page), refetchInterval: 60_000 });
  const refresh = () => client.invalidateQueries({ queryKey: ["presence", "staff", makerspaceId, "roster"] });
  const checkOut = useMutation({ mutationFn: (accountId: number) => presenceApi.staffCheckOut(makerspaceId, accountId), onSuccess: refresh });
  const rows = roster.data?.results ?? [];
  return <section aria-label={t`Present now`} className="grid gap-3">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm text-muted">{roster.data ? plural(roster.data.count, { one: "# person checked in now.", other: "# people checked in now." }) : t`People checked in now.`}</p>
      <button type="button" className="desk-button-brand" onClick={() => setCheckInOpen(true)}>{t`Check someone in`}</button>
    </div>
    {roster.isError ? <p role="alert" className="text-sm text-danger">{presenceErrorText(roster.error).text}</p> : null}
    <DataTable<PresenceRosterRow> caption={t`People present now`} data={rows} loading={roster.isLoading} getRowId={(row) => row.account_id}
      emptyTitle={t`No one is checked in`} emptyDescription={t`Self check-ins and staff check-ins appear here.`}
      columns={[
        { key: "display_name", header: t`Person`, render: (row) => <div className="flex items-center gap-3"><IdentityChip identity={{ kind: "avatar", name: row.display_name, seed: String(row.account_id) }} /><span>{row.display_name}</span></div> },
        { key: "status", header: t`Status`, render: (row) => STATUS_LABELS[row.status] ?? row.status },
        { key: "role_label", header: t`Role` },
        { key: "started_at", header: t`Since`, render: (row) => <time className="tabular-nums" dateTime={row.started_at}>{clockTime(row.started_at)}</time> },
        { key: "expires_at", header: t`Until`, render: (row) => <time className="tabular-nums" dateTime={row.expires_at}>{clockTime(row.expires_at)}</time> },
        { key: "actions", header: <span className="sr-only">{t`Actions`}</span>, render: (row) => <div className="flex flex-wrap gap-2">
          <button type="button" className="desk-button" aria-label={t`Related to ${row.display_name}`} onClick={() => setRelated(row)}>{t`Related`}</button>
          <button type="button" className="desk-button"
            disabled={checkOut.isPending} aria-label={t`Check out ${row.display_name}`} onClick={() => checkOut.mutate(row.account_id)}>{t`Check out`}</button></div> },
      ]} />
    {checkOut.error ? <p role="alert" className="text-sm text-danger">{presenceErrorText(checkOut.error).text}</p> : null}
    <MembershipPagination label={t`present people`} page={page} next={roster.data?.next} previous={roster.data?.previous} fetching={roster.isFetching} onPage={setPage} />
    {related ? <PresenceRelatedDialog makerspaceId={makerspaceId} accountId={related.account_id} name={related.display_name} onClose={() => setRelated(null)} /> : null}
    {checkInOpen ? <StaffCheckInDialog makerspaceId={makerspaceId} presets={presets} onClose={() => setCheckInOpen(false)} onDone={() => { setCheckInOpen(false); void refresh(); }} /> : null}
  </section>;
}
