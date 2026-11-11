import { t } from "@lingui/core/macro";
import { useState } from "react";
import { EmptyState, ErrorText, Field, ListRow, Pagination, RelativeTime, Skeleton, StatusPill } from "../../../components/ui";
import { HostingRequestDrawer } from "./HostingRequestDrawer";
import { hostingStatusLabels, isSelfHost, requestedKind, useHostingRequests, type HostingRequestState } from "./onboardingApi";
import { spaceNounTitle, type SpaceKind } from "../../../lib/spaceNoun";
import { PAGE_SIZE } from "./spacesApi";

export const SELF_HOST_NOTE = "Onboarding requests appear once this install hosts other makerspaces (set the platform domain).";

/** The managed-hosting queue. A self-hosted deployment answers 404, and the section shrinks to one line. */
export function OnboardingSection() {
  const [status, setStatus] = useState("submitted");
  const [kind, setKind] = useState<SpaceKind | "">("");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<number | null>(null);
  const list = useHostingRequests(status, page, kind);
  if (isSelfHost(list.error)) return <p className="text-sm text-muted">{SELF_HOST_NOTE}</p>;
  // The server filters by `requested_kind`; this repeats it on the page so an older server never mixes kinds in.
  const rows = (list.data?.results ?? []).filter(row => !kind || requestedKind(row) === kind);
  return <div className="grid gap-4">
    <div className="flex flex-wrap gap-4">
      <Field label={t`Status`} className="w-full max-w-xs">
        <select className="desk-input" value={status} onChange={event => { setStatus(event.target.value); setPage(1); }}>
          <option value="">{t`Every status`}</option>
          {(Object.entries(hostingStatusLabels()) as [HostingRequestState, string][]).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </Field>
      <Field label={t`Kind`} className="w-full max-w-xs">
        <select className="desk-input" value={kind} onChange={event => { setKind(event.target.value as SpaceKind | ""); setPage(1); }}>
          <option value="">{t`Makerspaces and organizations`}</option>
          <option value="makerspace">{t`Makerspaces`}</option>
          <option value="organization">{t`Organizations`}</option>
        </select>
      </Field>
    </div>
    {list.isLoading ? <Skeleton className="h-24 w-full" />
      : list.isError ? <ErrorText resource={t`hosting requests`} onRetry={() => { void list.refetch(); }} />
      : !rows.length ? <EmptyState message={t`No hosting requests with this status.`} />
      : <div className="grid gap-3">{rows.map(row => <ListRow key={row.id} title={row.space_name} onClick={() => setOpenId(row.id)}
        meta={<>{spaceNounTitle(requestedKind(row))} · {row.applicant_name}{row.location ? ` · ${row.location}` : ""}{row.expected_members ? t` · ${row.expected_members} expected members` : ""} · <RelativeTime date={row.created_at} /></>}
        right={<StatusPill label={hostingStatusLabels()[row.status] ?? row.status} tone={row.status === "rejected" ? "danger" : row.status === "accepted" ? "success" : "warn"} />} />)}</div>}
    <Pagination page={page} totalPages={Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))} onChange={setPage}
      count={list.data?.count} pageSize={PAGE_SIZE} disabled={list.isFetching} />
    {openId !== null ? <HostingRequestDrawer id={openId} onClose={() => setOpenId(null)} /> : null}
  </div>;
}
