import { plural, t } from "@lingui/core/macro";
import { useState } from "react";

import { EmptyState, ErrorBlock, ErrorText, ListRow, OverflowMenu, RelativeTime, Skeleton, StatusPill, PagePager } from "../../components/ui";
import type { OrganizationDetail } from "./organizationsApi";
import { useUpdateOrganizationMember } from "../organizations/organizationSelfServiceApi";
import { useOrganizationMemberships } from "./organizationsApi";

/** Governance actions get plain names; makerspace action codes stay readable as a fallback. */
const actionLabel = (action: string) => ({ manage_organization_profile: t`Manage organization profile`,
  manage_organization_members: t`Manage organization members` } as Record<string, string>)[action] ?? action.replace(/_/g, " ");
const actionList = (actions: string[]) => actions.map(actionLabel).join(", ") || t`none`;

export function OrganizationMemberships({ organization }: { organization: OrganizationDetail }) {
  const update = useUpdateOrganizationMember(organization.id);
  const [page, setPage] = useState(1);
  const enabled = organization.governance_actions.includes("manage_organization_members");
  const memberships = useOrganizationMemberships(organization.id, page, enabled);
  if (!enabled) return null;

  return (
    <section className="rounded-xl border border-line bg-bg p-4" aria-labelledby="organization-members-heading">
      <h3 className="title-section" id="organization-members-heading">{t`Memberships`}</h3>
      {memberships.isLoading ? <Skeleton className="mt-3 h-28 w-full" /> : null}
      {update.error ? <ErrorBlock className="mt-3" error={update.error} /> : null}
      <p className="mt-2 text-sm text-muted">{t`Invite another governor before removing the last governor. Changing authority requires recent identity verification.`}</p>
      {memberships.error ? <ErrorText resource={t`organization members`} onRetry={() => { void memberships.refetch(); }} /> : null}
      {memberships.data && !memberships.data.results.length ? <EmptyState message={t`It's just you so far. Create an invitation to bring in your team.`} /> : null}
      {memberships.data?.results.length ? (
        <div className="mt-3 grid gap-3">{memberships.data.results.map(member => <ListRow key={member.id}
          title={member.display_name || member.username}
          identity={{ kind: "avatar", name: member.display_name || member.username, seed: String(member.user_id) }}
          meta={<><span className="[overflow-wrap:anywhere]">{member.email}</span> {t` · Joined `}<RelativeTime date={member.created_at} /><br />{t`Governance: ${actionList(member.governance_actions)}`}
            <br />{t`Makerspace actions: ${actionList(member.granted_actions)}`}</>}
          right={<div className="flex flex-wrap items-center gap-2"><StatusPill label={member.status === "active" ? t`Active` : member.status === "suspended" ? t`Suspended` : member.status} tone={member.status === "active" ? "success" : "warn"} />
            <OverflowMenu label={t`Manage ${member.display_name || member.username}`} actions={[
              { label: member.status === "active" ? t`Suspend` : t`Reactivate`, tone: member.status === "active" ? "danger" : "default", pending: update.isPending,
                onClick: () => update.mutate({ memberId: member.id, status: member.status === "active" ? "suspended" : "active" }),
                ...(member.status === "active" ? { confirm: { title: t`Suspend this member?`, message: t`They lose this organization's authority until reactivated.`, confirmLabel: t`Suspend` } } : {}) },
              ...(["governance_actions", "granted_actions"] as const).flatMap(field =>
                [...new Set([...member[field], ...organization[field]])].map(action => ({
                  label: member[field].includes(action) ? t`Revoke ${actionLabel(action)}` : t`Grant ${actionLabel(action)}`,
                  pending: update.isPending,
                  // Existing target actions stay revocable even when the actor
                  // lacks them; only held actions appear as possible additions.
                  onClick: () => update.mutate({ memberId: member.id, [field]: member[field].includes(action)
                    ? member[field].filter(value => value !== action) : [...member[field], action] }),
                }))),
            ]} /></div>} />)}</div>
      ) : null}
      {memberships.data ? (
        <div className="mt-3 grid gap-2">
          <p className="tabular-nums text-xs text-muted">{plural(memberships.data.count, { one: "# member", other: "# members" })}</p>
          <PagePager page={page} setPage={setPage} next={memberships.data.next} />
        </div>
      ) : null}
    </section>
  );
}
