import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { EmptyState, ListRow, StatusPill } from "../../components/ui";
import { formatDate } from "../../lib/format";
import { accessKeys, getMyAccess } from "./api";
import { LogoLoader } from "../../components/LogoLoader";

const everyMachineOf = (typeName: string | null) => { const label = typeName ?? ""; return t`Every ${label} machine`; };

/** "My machine access": what a space manager has let you use, and the machines open to every member. */
export function MemberMachineAccess({ makerspaceId }: { makerspaceId: number }) {
  const query = useQuery({ queryKey: accessKeys.mine(makerspaceId), queryFn: () => getMyAccess(makerspaceId) });
  const empty = query.isSuccess && !query.data.grants.length && !query.data.open_machines.length;
  return <section className="desk-panel p-5" aria-label={t`My machine access`}>
    <h2 className="title-panel">{t`My machine access`}</h2>
    {query.isLoading ? <LogoLoader label={t`Loading your machine access…`} size={48} className="min-h-16 py-3" /> : null}
    {query.error instanceof Error ? <p role="alert" className="text-danger">{query.error.message}</p> : null}
    {empty ? <EmptyState message={t`You have not been given access to any machine yet. Ask a space manager.`} /> : null}
    <ul className="mt-3 grid gap-3">{query.data?.grants.map(row => <li key={row.id}><ListRow
      title={row.machine_name ?? everyMachineOf(row.machine_type_name)}
      identity={{ kind: "icon", icon: "Wrench", tone: row.status === "live" ? "success" : "neutral" }}
      meta={<>{t`Given ${formatDate(row.granted_at)}`}<span className="block">{row.expires_at ? t`Ends ${formatDate(row.expires_at)}` : t`No end date`}</span>
        {row.status === "expired" ? <span className="mt-1 block text-warn-ink">{t`This access has ended. Ask a space manager to renew it.`}</span> : null}</>}
      right={<StatusPill label={row.status === "live" ? t`Has access` : t`Ended`} tone={row.status === "live" ? "success" : "warn"} />} /></li>)}</ul>
    {query.data?.open_machines.length ? <div className="mt-4"><h3 className="title-section">{t`Open to all members`}</h3>
      <ul className="mt-2 grid gap-1 text-sm">{query.data.open_machines.map(row => <li key={row.id}>{row.name}</li>)}</ul></div> : null}
  </section>;
}
