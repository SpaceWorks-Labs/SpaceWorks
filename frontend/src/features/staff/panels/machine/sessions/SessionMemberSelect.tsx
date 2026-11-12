import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { staffRequest } from "../../../../../lib/api";
import { SearchField } from "../../../../../components/ui/SearchField";

type Candidate = { user_id: number; display_name: string; username: string };

/** Pick a member of the space for a machine, from the same candidate list manual usage uses. */
export function SessionMemberSelect({ machineId, value, onChange, label = t`Member`, anyLabel }: {
  machineId: number; value: string; onChange: (value: string) => void; label?: string;
  /** As a list filter: the empty choice means "everyone" and nothing is required. */
  anyLabel?: string;
}) {
  const [search, setSearch] = useState("");
  const candidates = useQuery({
    queryKey: ["machines", machineId, "usage-members", search],
    queryFn: () => staffRequest<{ count: number; results: Candidate[] }>(
      `/admin/machines/${machineId}/usage-candidates?q=${encodeURIComponent(search)}`),
    enabled: machineId > 0,
  });
  return <div className="grid gap-2 sm:grid-cols-2">
    <label className="eyebrow grid gap-1">{t`Find member`}<SearchField className="desk-input" value={search} onChange={event => setSearch(event.target.value)} placeholder={t`Search by name`}
        disabled={!machineId} />
    </label>
    <label className="eyebrow grid gap-1">{label}
      <select className="desk-input" value={value} required={!anyLabel} disabled={!machineId || candidates.isLoading}
        onChange={event => onChange(event.target.value)}>
        <option value="">{anyLabel ?? t`Choose a member`}</option>
        {candidates.data?.results.map(row => <option key={row.user_id} value={row.user_id}>{row.display_name || row.username}</option>)}
      </select>
    </label>
    {candidates.error instanceof Error ? <p role="alert" className="text-sm text-danger sm:col-span-2">{candidates.error.message}</p> : null}
  </div>;
}
