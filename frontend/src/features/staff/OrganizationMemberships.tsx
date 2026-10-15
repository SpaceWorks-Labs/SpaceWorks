import { plural } from "../../lib/plural";
import { useState } from "react";

import { EmptyState, ErrorText, ListRow, RelativeTime, Skeleton, StatusPill } from "../../components/ui";
import type { OrganizationDetail } from "./organizationsApi";
import { useOrganizationMemberships } from "./organizationsApi";

export function OrganizationMemberships({ organization }: { organization: OrganizationDetail }) {
  const [page, setPage] = useState(1);
  const enabled = organization.governance_actions.includes("manage_organization_members");
  const memberships = useOrganizationMemberships(organization.id, page, enabled);
  if (!enabled) return null;

  return (
    <section className="rounded-xl border border-line bg-bg p-4" aria-labelledby="organization-members-heading">
      <h3 className="title-section" id="organization-members-heading">Memberships</h3>
      {memberships.isLoading ? <Skeleton className="mt-3 h-28 w-full" /> : null}
      {memberships.error ? <ErrorText resource="organization members" onRetry={() => { void memberships.refetch(); }} /> : null}
      {memberships.data && !memberships.data.results.length ? <EmptyState message="It's just you so far. Create an invitation to bring in your team." /> : null}
      {memberships.data?.results.length ? (
        <div className="mt-3 grid gap-3">{memberships.data.results.map(member => <ListRow key={member.id}
          title={member.display_name || member.username}
          identity={{ kind: "avatar", name: member.display_name || member.username, seed: String(member.user_id) }}
          meta={<><span className="[overflow-wrap:anywhere]">{member.email}</span> · Joined <RelativeTime date={member.created_at} /><br />Governance: {member.governance_actions.map(action => action.replace(/_/g, " ")).join(", ") || "none"}
            <br />Makerspace actions: {member.granted_actions.map(action => action.replace(/_/g, " ")).join(", ") || "none"}</>}
          right={<StatusPill label={member.status} tone={member.status === "active" ? "success" : "warn"} />} />)}</div>
      ) : null}
      {memberships.data ? (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <button className="desk-button" type="button" disabled={!memberships.data.previous} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</button>
          <span className="tabular-nums text-xs text-muted">Page {page} · {plural(memberships.data.count, "member")}</span>
          <button className="desk-button" type="button" disabled={!memberships.data.next} onClick={() => setPage((value) => value + 1)}>Next</button>
        </div>
      ) : null}
    </section>
  );
}
