import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../../../lib/api";

type Candidate = { user_id: number; display_name: string; username: string };
type Page = { count: number; results: Candidate[] };

export function UsageAttributionFields({ machineId, member, startedAt, onChange }: {
  machineId: number;
  member: string;
  startedAt: string;
  onChange: (value: { member?: string; started_at?: string }) => void;
}) {
  const [search, setSearch] = useState("");
  const candidates = useQuery({
    queryKey: ["machines", machineId, "usage-members", search],
    queryFn: () => staffRequest<Page>(`/admin/machines/${machineId}/usage-candidates?q=${encodeURIComponent(search)}`),
    enabled: machineId > 0,
  });
  return <>
    <label className="eyebrow grid gap-1">{t`Find member (optional)`}<input className="desk-input" value={search} onChange={event => setSearch(event.target.value)} placeholder={t`Search by name`} disabled={!machineId} />
    </label>
    <label className="eyebrow grid gap-1">{t`Member (optional)`}<select className="desk-input" value={member} disabled={!machineId || candidates.isLoading}
        onChange={event => onChange({ member: event.target.value })}>
        <option value="">{t`Unattributed`}</option>
        {member && !candidates.data?.results.some(row => String(row.user_id) === member) ? <option value={member}>{t`Selected member #${member}`}</option> : null}
        {candidates.data?.results.map(row => <option key={row.user_id} value={row.user_id}>{row.display_name}</option>)}
      </select>
      {(candidates.data?.count ?? 0) > 24 ? <span className="text-muted">{t`Refine your search to find more members.`}</span> : null}
    </label>
    <label className="eyebrow grid gap-1">{t`Started at (optional, local time)`}<input className="desk-input" type="datetime-local" value={startedAt} onChange={event => onChange({ started_at: event.target.value })} />
    </label>
    {candidates.error instanceof Error ? <p className="text-sm text-danger">{candidates.error.message}</p> : null}
  </>;
}
