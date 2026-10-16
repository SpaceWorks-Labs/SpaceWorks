import { plural } from "../../lib/plural";
import { useState } from "react";

import { EmptyState, ErrorBlock, ErrorText, ListRow, OverflowMenu, RelativeTime, Skeleton, StatusPill } from "../../components/ui";
import type { OrganizationDetail } from "./organizationsApi";
import { useUpdateOrganizationMember } from "../organizations/organizationSelfServiceApi";
import { useOrganizationMemberships } from "./organizationsApi";

export function OrganizationMemberships({ organization }: { organization: OrganizationDetail }) {
  const update = useUpdateOrganizationMember(organization.id);
  const [page, setPage] = useState(1);
  const enabled = organization.governance_actions.includes("manage_organization_members");
  const memberships = useOrganizationMemberships(organization.id, page, enabled);
  if (!enabled) return null;

  return (
    <section className="rounded-xl border border-line bg-bg p-4" aria-labelledby="organization-members-heading">
      <h3 className="title-section" id="organization-members-heading">Memberships</h3>
      {memberships.isLoading ? <Skeleton className="mt-3 h-28 w-full" /> : null}
      {update.error ? <ErrorBlock className="mt-3" error={update.error} /> : null}
      <p className="mt-2 text-sm text-muted">Invite another governor before removing the last governor. Changing authority requires recent identity verification.</p>
      {memberships.error ? <ErrorText resource="organization members" onRetry={() => { void memberships.refetch(); }} /> : null}
      {memberships.data && !memberships.data.results.length ? <EmptyState message="It's just you so far. Create an invitation to bring in your team." /> : null}
      {memberships.data?.results.length ? (
        <div className="mt-3 grid gap-3">{memberships.data.results.map(member => <ListRow key={member.id}
          title={member.display_name || member.username}
          identity={{ kind: "avatar", name: member.display_name || member.username, seed: String(member.user_id) }}
          meta={<><span className="[overflow-wrap:anywhere]">{member.email}</span> · Joined <RelativeTime date={member.created_at} /><br />Governance: {member.governance_actions.map(action => action.replace(/_/g, " ")).join(", ") || "none"}
            <br />Makerspace actions: {member.granted_actions.map(action => action.replace(/_/g, " ")).join(", ") || "none"}</>}
          right={<div className="flex flex-wrap items-center gap-2"><StatusPill label={member.status} tone={member.status === "active" ? "success" : "warn"} />
            <OverflowMenu label={`Manage ${member.display_name || member.username}`} actions={[
              { label: member.status === "active" ? "Suspend" : "Reactivate", tone: member.status === "active" ? "danger" : "default", pending: update.isPending,
                onClick: () => update.mutate({ memberId: member.id, status: member.status === "active" ? "suspended" : "active" }),
                ...(member.status === "active" ? { confirm: { title: "Suspend this member?", message: "They lose this organization's authority until reactivated.", confirmLabel: "Suspend" } } : {}) },
              ...(["governance_actions", "granted_actions"] as const).flatMap(field =>
                [...new Set([...member[field], ...organization[field]])].map(action => ({
                  label: `${member[field].includes(action) ? "Revoke" : "Grant"} ${action.replace(/_/g, " ")}`,
                  pending: update.isPending,
                  // Existing target actions stay revocable even when the actor
                  // lacks them; only held actions appear as possible additions.
                  onClick: () => update.mutate({ memberId: member.id, [field]: member[field].includes(action)
                    ? member[field].filter(value => value !== action) : [...member[field], action] }),
                }))),
            ]} /></div>} />)}</div>
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
