import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { memberRequest } from "../../lib/api";
import { OrganizationLeaveCard } from "./OrganizationLeaveCard";
import { PagePager } from "../../components/ui";

type OwnOrganization = { id: number; name: string; slug: string; leave_state: { membership_version: number; allowed_actions: string[]; reason: string | null } };
export function OwnOrganizations() {
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["member", "own-organizations", page], gcTime: 0, retry: false,
    queryFn: () => memberRequest<{ count: number; next: string | null; previous: string | null; results: OwnOrganization[] }>(`/member/organizations/?page=${page}`) });
  if (query.isPending) return <p role="status">{t`Loading your organizations…`}</p>;
  if (query.error) return <div><p role="alert" className="text-danger">{query.error.message}</p><button className="desk-button" onClick={() => void query.refetch()}>{t`Retry organizations`}</button></div>;
  return <section className="grid gap-4" aria-label={t`Your organizations`}><h2 className="title-section">{t`Your organizations`}</h2>
    {query.data.results.length ? query.data.results.map(row => row.leave_state.allowed_actions.includes("leave") ? <OrganizationLeaveCard key={row.id} organizationId={row.id} name={row.name} version={row.leave_state.membership_version} onLeft={() => { void query.refetch(); }} />
      : <p key={row.id}>{t`Appoint another organization owner before leaving ${row.name}.`}</p>) : <p>{t`You do not belong to any organizations.`}</p>}
    <PagePager page={page} setPage={setPage} next={query.data.next} />
  </section>;
}
