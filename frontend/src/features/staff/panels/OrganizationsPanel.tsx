import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";

import { ErrorBlock, ListRow, PagePager } from "../../../components/ui";
import { DashboardLayout } from "../../../components/layouts/DashboardLayout";
import { SettingsLayout } from "../../../components/layouts/SettingsLayout";
import { useTenant } from "../../../lib/tenant";
import { OrganizationSelfCreation, useOrganizationSelfCreationVisible } from "../../organizations/OrganizationSelfCreation";
import { useDeleteOrganization } from "../../organizations/organizationSelfServiceApi";
import { OrganizationInvitations } from "../OrganizationInvitations";
import { HostingInvitations } from "../HostingInvitations";
import { useHostingAvailability } from "../../hosting/hostingApi";
import { OrganizationMemberships } from "../OrganizationMemberships";
import { OrganizationProfileForm } from "../OrganizationProfileForm";
import { OrganizationEmailSender } from "../OrganizationEmailSender";
import { OrganizationHoursBankBalance } from "../OrganizationHoursBankBalance";
import { useOrganization, useOrganizations } from "../organizationsApi";
import type { Makerspace } from "./shared";
import { OrganizationCreate, OrganizationLinks } from "../OrganizationSetup";
import { PublicPageBuilder } from "../../publicPages/PublicPageBuilder";
import { OrganizationReviewStatus } from "../../organizations/review/OrganizationReviewStatus";
import { OrganizationMemberRollup } from "../../organizations/OrganizationMemberRollup";
import { EventInsightsCard, organizationInsightsPath } from "../eventProgramme/EventInsightsCard";

export function OrganizationsPanel({ isSuperadmin = false, makerspaces = [] }: { isSuperadmin?: boolean; makerspaces?: Makerspace[] }) {
  const [page, setPage] = useState(1);
  const organizations = useOrganizations(page);
  const [selectedId, setSelectedId] = useState<number | null>(() => Number(new URLSearchParams(window.location.search).get("org")) || null);
  const [creating, setCreating] = useState(false);
  const detail = useOrganization(selectedId);
  const select = (id: number | null) => {
    setSelectedId(id);
    const url = new URL(window.location.href);
    if (id) url.searchParams.set("org", String(id)); else url.searchParams.delete("org");
    window.history.replaceState(null, "", url);
  };

  useEffect(() => {
    if (selectedId === null && organizations.data?.count === 1 && organizations.data.results[0]) {
      setSelectedId(organizations.data.results[0].id);
    }
  }, [organizations.data, selectedId]);

  const tenant = useTenant();
  // Hooks cannot be conditional; the mutation only fires from the danger zone, which renders with a loaded detail.
  const remove = useDeleteOrganization(selectedId ?? 0);
  const canManageMembers = Boolean(detail.data?.governance_actions.includes("manage_organization_members"));
  // Hosting invitations are a central-origin flow; the section only appears while the platform takes requests.
  const hostingScope = canManageMembers && tenant.mode === "central";
  const canInviteHosting = useHostingAvailability(hostingScope) && hostingScope;
  // Deleting needs both governance actions; the server still re-checks recent identity verification.
  const canDelete = ["manage_organization_members", "manage_organization_profile"].every(action => detail.data?.governance_actions.includes(action));
  // The page editor locks to a non-platform governor holding the profile action; nobody else gets a builder the server refuses.
  const canEditPage = !isSuperadmin && Boolean(detail.data?.governance_actions.includes("manage_organization_profile"));
  // Superadmins create through the platform flow; everyone else gets the rate-limited self-service flow,
  // which only exists on the central origin (global organization operations are tenant-unbound) and only
  // while the platform policy allows it, so a switched-off policy never opens an empty create page.
  const canSelfCreate = useOrganizationSelfCreationVisible(!isSuperadmin && tenant.mode === "central");
  const createAction = isSuperadmin || canSelfCreate ? { label: t`Create organization`, onClick: () => setCreating(true) } : undefined;
  if (creating && isSuperadmin) return <OrganizationCreate onClose={() => setCreating(false)} onCreated={id => { setCreating(false); select(id); }} />;
  if (creating) return <SettingsLayout
    header={{ title: t`Create your organization`, subtitle: t`A private profile you govern. Linking makerspaces needs platform approval.`,
      secondary: { label: t`Back to organizations`, onClick: () => setCreating(false) } }}
    state={{ status: "ready" }}
    sections={[{ id: "org-self-create", title: t`Organization profile`, rows: <OrganizationSelfCreation onCreated={id => { setCreating(false); select(id); }} /> }]} />;
  if (selectedId !== null) return <SettingsLayout
    header={{ title: detail.data?.name ?? t`Organization`, subtitle: t`Your public profile, people and connected spaces.`,
      secondary: detail.data?.public_profile_enabled ? { label: t`View public page ↗`, href: `/o/${detail.data.slug}`, external: true } : undefined,
      primary: canManageMembers ? { label: t`Invite someone`, onClick: () => document.getElementById("org-invitations")?.scrollIntoView({ behavior: "smooth" }) } : undefined,
      overflow: [
        ...(organizations.data && organizations.data.count > 1 ? [{ label: t`All organizations`, onClick: () => select(null) }] : []),
        ...(createAction ? [createAction] : []),
      ] }}
    state={{ status: detail.isLoading ? "loading" : detail.isError ? "error" : "ready", error: t`Couldn't load organization. Try again.`, onRetry: () => { void detail.refetch(); } }}
    tabs={[
      { key: "profile", label: t`Profile`, href: `?org=${selectedId}&section=profile#org-profile` },
      ...(canEditPage ? [{ key: "public-page", label: t`Public page`, href: `?org=${selectedId}&section=public-page#org-public-page` }] : []),
      ...(canManageMembers ? [{ key: "people", label: t`People`, href: `?org=${selectedId}&section=people#org-people` },
        { key: "invitations", label: t`Invitations`, href: `?org=${selectedId}&section=invitations#org-invitations` }] : []),
      ...(isSuperadmin ? [{ key: "spaces", label: t`Spaces`, href: `?org=${selectedId}&section=spaces#org-spaces` }] : []),
    ]} activeTab={new URLSearchParams(window.location.search).get("section") ?? "profile"}
    sections={detail.data ? [
      // O-B5: an organization that is not approved leads with where its review stands and what comes next.
      ...(((detail.data as { review_status?: string }).review_status ?? "approved") !== "approved"
        ? [{ id: "org-review", title: t`Review status`, rows: <OrganizationReviewStatus organization={detail.data} /> }] : []),
      { id: "org-profile", title: t`Profile`, rows: <OrganizationProfileForm organization={detail.data} /> },
      ...(detail.data.governance_actions.includes("manage_organization_profile") || isSuperadmin
        ? [{ id: "org-email-sender", title: t`Event email sender`, rows: <OrganizationEmailSender organizationId={detail.data.id} /> }] : []),
      // Open item B13: read-only hours balance for organization admins (renders nothing when no space gave one).
      // Parity E-F3 (A21): the organisation's hosted events, across spaces where events.space_insights is on. Counts only.
      ...(detail.data.governance_actions.length ? [{ id: "org-event-insights", title: t`Event insights`, rows: <EventInsightsCard path={organizationInsightsPath(detail.data.id)} /> }] : []),
      ...(detail.data.governance_actions.length ? [{ id: "org-hours", title: t`Included hours`, rows: <OrganizationHoursBankBalance organizationId={detail.data.id} /> }] : []),
      ...(canEditPage ? [{ id: "org-public-page", title: t`Public page`, rows: <PublicPageBuilder owner={{ kind: "organization", id: detail.data.id }} /> }] : []),
      // Without member rights both components render nothing, so their tabs and headings go too.
      ...(canManageMembers ? [{ id: "org-member-rollup", title: t`Members across spaces`, rows: <OrganizationMemberRollup organizationId={detail.data.id} /> },
        { id: "org-people", title: t`People`, rows: <OrganizationMemberships organization={detail.data} /> },
        { id: "org-invitations", title: t`Invitations`, rows: <OrganizationInvitations organization={detail.data} /> }] : []),
      ...(canInviteHosting ? [{ id: "org-hosting", title: t`Invite a makerspace`, rows: <HostingInvitations key={detail.data.id} scope={{ organizationId: detail.data.id }} /> }] : []),
      ...(isSuperadmin ? [{ id: "org-spaces", title: t`Spaces`, rows: <OrganizationLinks key={detail.data.id} id={detail.data.id} makerspaces={makerspaces} /> }] : []),
      ...(canDelete && remove.error ? [{ id: "org-delete-error", title: t`Couldn't delete organization`, rows: <ErrorBlock error={remove.error} /> }] : []),
    ] : []}
    danger={detail.data && canDelete ? [{ title: t`Delete organization`,
      consequence: t`Permanently removes this unlinked organization, its memberships and invitations; the audit history remains. Linked makerspaces, event references or retained artwork prevent deletion, and it requires recent identity verification.`,
      action: { label: t`Delete organization`, pending: remove.isPending, pendingLabel: t`Deleting…`,
        confirm: { title: t`Delete ${detail.data.name}?`, message: t`This permanently removes this unlinked organization, its memberships and invitations.`, confirmLabel: t`Delete organization` },
        onClick: () => remove.mutate(undefined, { onSuccess: () => { select(null); setPage(1); } }) } }] : []} />;
  return <DashboardLayout header={{ eyebrow: t`Space Works`, title: t`Organizations`, subtitle: t`Your teams, people and connected makerspaces.`, primary: createAction }}
    state={{ status: organizations.isLoading ? "loading" : organizations.isError ? "error" : "ready", error: t`Couldn't load organizations. Try again.`, onRetry: () => { void organizations.refetch(); } }} stats={[]}
    main={[{ title: t`Your organizations`, isEmpty: !organizations.data?.results.length,
      empty: { message: canSelfCreate ? t`You're not part of an organization yet. Ask an organization admin for an invite, or create your own.` : t`You're not part of an organization yet. Ask an organization admin for an invite.`, action: createAction },
      content: <div className="grid gap-3 sm:grid-cols-2">{organizations.data?.results.map(org => <ListRow key={org.id} title={org.name} identity={{ kind: "avatar", name: org.name, seed: String(org.id) }} meta={org.slug} onClick={() => select(org.id)} />)}</div> }]}
    progress={organizations.data ? <PagePager page={page} setPage={setPage} next={organizations.data.next} /> : undefined} />;
}
