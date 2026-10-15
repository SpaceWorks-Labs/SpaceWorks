import { useEffect, useState } from "react";

import { ListRow } from "../../../components/ui";
import { DashboardLayout } from "../../../components/layouts/DashboardLayout";
import { SettingsLayout } from "../../../components/layouts/SettingsLayout";
import { OrganizationInvitations } from "../OrganizationInvitations";
import { OrganizationMemberships } from "../OrganizationMemberships";
import { OrganizationProfileForm } from "../OrganizationProfileForm";
import { useOrganization, useOrganizations } from "../organizationsApi";
import type { Makerspace } from "./shared";
import { OrganizationCreate, OrganizationLinks } from "../OrganizationSetup";

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

  const canManageMembers = Boolean(detail.data?.governance_actions.includes("manage_organization_members"));
  if (creating) return <OrganizationCreate onClose={() => setCreating(false)} onCreated={id => { setCreating(false); select(id); }} />;
  if (selectedId !== null) return <SettingsLayout
    header={{ title: detail.data?.name ?? "Organization", subtitle: "Your public profile, people and connected spaces.",
      secondary: detail.data?.public_profile_enabled ? { label: "View public page ↗", href: `/o/${detail.data.slug}`, external: true } : undefined,
      primary: canManageMembers ? { label: "Invite someone", onClick: () => document.getElementById("org-invitations")?.scrollIntoView({ behavior: "smooth" }) } : undefined,
      overflow: [
        ...(organizations.data && organizations.data.count > 1 ? [{ label: "All organizations", onClick: () => select(null) }] : []),
        ...(isSuperadmin ? [{ label: "Create organization", onClick: () => setCreating(true) }] : []),
      ] }}
    state={{ status: detail.isLoading ? "loading" : detail.isError ? "error" : "ready", error: "Couldn't load organization. Try again.", onRetry: () => { void detail.refetch(); } }}
    tabs={[
      { key: "profile", label: "Profile", href: `?org=${selectedId}&section=profile#org-profile` },
      ...(canManageMembers ? [{ key: "people", label: "People", href: `?org=${selectedId}&section=people#org-people` },
        { key: "invitations", label: "Invitations", href: `?org=${selectedId}&section=invitations#org-invitations` }] : []),
      ...(isSuperadmin ? [{ key: "spaces", label: "Spaces", href: `?org=${selectedId}&section=spaces#org-spaces` }] : []),
    ]} activeTab={new URLSearchParams(window.location.search).get("section") ?? "profile"}
    sections={detail.data ? [
      { id: "org-profile", title: "Profile", rows: <OrganizationProfileForm organization={detail.data} /> },
      // Without member rights both components render nothing, so their tabs and headings go too.
      ...(canManageMembers ? [{ id: "org-people", title: "People", rows: <OrganizationMemberships organization={detail.data} /> },
        { id: "org-invitations", title: "Invitations", rows: <OrganizationInvitations organization={detail.data} /> }] : []),
      ...(isSuperadmin ? [{ id: "org-spaces", title: "Spaces", rows: <OrganizationLinks key={detail.data.id} id={detail.data.id} makerspaces={makerspaces} /> }] : []),
    ] : []} />;
  return <DashboardLayout header={{ eyebrow: "Space Works", title: "Organizations", subtitle: "Your teams, people and connected makerspaces.", primary: isSuperadmin ? { label: "Create organization", onClick: () => setCreating(true) } : undefined }}
    state={{ status: organizations.isLoading ? "loading" : organizations.isError ? "error" : "ready", error: "Couldn't load organizations. Try again.", onRetry: () => { void organizations.refetch(); } }} stats={[]}
    main={[{ title: "Your organizations", isEmpty: !organizations.data?.results.length,
      empty: { message: "You're not part of an organization yet. Ask an organization admin for an invite.", action: isSuperadmin ? { label: "Create organization", onClick: () => setCreating(true) } : undefined },
      content: <div className="grid gap-3 sm:grid-cols-2">{organizations.data?.results.map(org => <ListRow key={org.id} title={org.name} identity={{ kind: "avatar", name: org.name, seed: String(org.id) }} meta={org.slug} onClick={() => select(org.id)} />)}</div> }]}
    progress={organizations.data && (organizations.data.previous || organizations.data.next) ? <div className="flex flex-wrap items-center gap-3"><button className="desk-button" disabled={!organizations.data.previous} onClick={() => setPage(value => Math.max(1, value - 1))}>Previous</button><span className="self-center text-sm text-muted">Page {page} · {organizations.data.count} organizations</span><button className="desk-button" disabled={!organizations.data.next} onClick={() => setPage(value => value + 1)}>Next</button></div> : undefined} />;
}
