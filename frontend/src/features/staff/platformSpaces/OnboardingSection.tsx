import { t } from "@lingui/core/macro";
import { useState } from "react";
import { EmptyState, ErrorText, Field, ListRow, Pagination, RelativeTime, Skeleton, StatusPill } from "../../../components/ui";
import { HostingRequestDrawer } from "./HostingRequestDrawer";
import { HOSTING_STATUS_LABELS, isSelfHost, useHostingRequests, type HostingRequestState } from "./onboardingApi";
import { PAGE_SIZE } from "./spacesApi";

export const SELF_HOST_NOTE = "Onboarding requests exist only on a managed deployment.";

/** The managed-hosting queue. A self-hosted deployment answers 404, and the section shrinks to one line. */
export function OnboardingSection() {
  const [status, setStatus] = useState("submitted");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<number | null>(null);
  const list = useHostingRequests(status, page);
  if (isSelfHost(list.error)) return <p className="text-sm text-muted">{SELF_HOST_NOTE}</p>;
  const rows = list.data?.results ?? [];
  return <div className="grid gap-4">
    <Field label={t`Status`} className="max-w-xs">
      <select className="desk-input" value={status} onChange={event => { setStatus(event.target.value); setPage(1); }}>
        <option value="">{t`Every status`}</option>
        {(Object.keys(HOSTING_STATUS_LABELS) as HostingRequestState[]).map(key => <option key={key} value={key}>{HOSTING_STATUS_LABELS[key]}</option>)}
      </select>
    </Field>
    {list.isLoading ? <Skeleton className="h-24 w-full" />
      : list.isError ? <ErrorText resource="hosting requests" onRetry={() => { void list.refetch(); }} />
      : !rows.length ? <EmptyState message={t`No hosting requests with this status.`} />
      : <div className="grid gap-3">{rows.map(row => <ListRow key={row.id} title={row.space_name} onClick={() => setOpenId(row.id)}
        meta={<>{row.applicant_name} · {row.location}{row.expected_members ? t` · ${row.expected_members} expected members` : ""} · <RelativeTime date={row.created_at} /></>}
        right={<StatusPill label={HOSTING_STATUS_LABELS[row.status] ?? row.status} tone={row.status === "rejected" ? "danger" : row.status === "accepted" ? "success" : "warn"} />} />)}</div>}
    <Pagination page={page} totalPages={Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))} onChange={setPage}
      count={list.data?.count} pageSize={PAGE_SIZE} disabled={list.isFetching} />
    {openId !== null ? <HostingRequestDrawer id={openId} onClose={() => setOpenId(null)} /> : null}
  </div>;
}
