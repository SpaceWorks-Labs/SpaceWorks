import { t } from "@lingui/core/macro";
import { consoleSessionHref } from "../../lib/api/sessionContext";
import { useRef, useState, type ReactNode } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { SettingsLayout, type SettingsLayoutSection } from "../../components/layouts";
import { useQuery } from "@tanstack/react-query";
import type { MakerspaceArchiveRequest } from "../../generated/api";

import { ErrorBlock, Modal } from "../../components/ui";
import { EmptyState } from "../../components/ui/EmptyState";
import { staffRequest } from "../../lib/api";
import { MakerspaceArchiveRequestPanel } from "./MakerspaceArchiveRequestPanel";
import { type Makerspace, useStaffGet } from "./StaffPanels";
import { SettingsHub } from "./SettingsHub";
import { SettingsSectionNav } from "./SettingsSectionNav";
import { AreaConsoleLink } from "./SettingsAreaConsoleLink";
import { settingsLinkEntry, settingsSectionHelp } from "./settingsHubCatalog";
import { useMakerspaceSettingsSections } from "./makerspaceSettingsSections";
import { orderedSettingsSections, settingsGroups, settingsLanding, settingsLinkTarget, settingsSectionAlias,
  settingsSectionForHash, settingsSectionFromSubPath } from "./settingsSections";
import { staffPathState, staffTabPath } from "./staffTabs";
import { nounOf, nounTitleOf } from "../../lib/spaceNoun";

type Props = {
  makerspace: Makerspace;
  isSuperadmin: boolean;
  canManageMakerspace: boolean;
  /** The actor's permitted tabs, so the menu and hub link only to settings pages they can open. */
  allowedTabs?: readonly string[];
  singleTenantLocked?: boolean;
};

/**
 * Makerspace settings as routed subpages, `/admin/settings/<section>`: one section per page,
 * grouped Space / People / Areas / Money / Communication / Integrations / Administration in
 * the side nav (decision 255). Pages that live on their own console tab (Staff & roles, the
 * Shop's settings, Security, …) sit in the same menu as links. `/admin/settings`, pre-split
 * `#section` bookmarks and retired subpages land on the right page.
 */
export function MakerspaceSettingsPanel({ makerspace, isSuperadmin, canManageMakerspace, allowedTabs = [], singleTenantLocked = false }: Props) {
  const location = useLocation();
  const content = useRef<HTMLDivElement>(null);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const settings = useStaffGet<Makerspace>(
    ["makerspace-settings", makerspace.id],
    `/admin/makerspaces/${makerspace.id}`,
  );
  // Same cache entry as the archive panel: a pending request must be visible on the page,
  // not only after opening the request form.
  const archiveRequests = useQuery({ queryKey: ["staff", "archive-requests", makerspace.id] as const, enabled: canManageMakerspace,
    queryFn: () => staffRequest<MakerspaceArchiveRequest[]>(`/admin/makerspace/${makerspace.id}/archive-requests`) });
  const archivePending = Boolean(archiveRequests.data?.some(request => request.status === "pending"));
  const sections = useMakerspaceSettingsSections({ makerspace, settings: settings.data, loading: settings.isLoading, isSuperadmin, canManageMakerspace });
  // Mirrors StaffWorkspace: a platform superadmin's console paths are unscoped.
  const slug = isSuperadmin ? undefined : makerspace.slug;
  const tabHref = (tab: string, view = "") => consoleSessionHref(staffTabPath(tab, false, slug, singleTenantLocked, view));
  const sectionHref = (section: string) => consoleSessionHref(staffTabPath("settings", false, slug, singleTenantLocked, section));
  // The overview goes first: search across every section and the settings pages beside it.
  sections.unshift({ id: "overview", title: t`Overview`, rows: <SettingsHub makerspace={settings.data ?? makerspace}
    sectionIds={sections.map(section => section.id)} allowedTabs={allowedTabs} tabHref={tabHref} sectionHref={sectionHref} /> });
  // Menu entries that open another console page, for the tabs this actor may open.
  const links = Object.fromEntries(settingsGroups().flatMap(group => group.items).flatMap(item => {
    const target = settingsLinkTarget(item);
    const entry = settingsLinkEntry(item);
    return target && entry && allowedTabs.includes(target.tab) ? [[item, { title: entry.title, href: tabHref(target.tab, target.view) }]] : [];
  }));

  // Decision 295: an organization workspace reads "Organization settings" / "this organization".
  const noun = nounOf(settings.data ?? makerspace);
  const nounTitle = nounTitleOf(settings.data ?? makerspace);
  const ids = orderedSettingsSections(sections.map(section => section.id));
  const requested = settingsSectionFromSubPath(staffPathState(location.pathname, false).subPath);
  if (!requested || (!ids.includes(requested) && settingsSectionAlias(requested))) {
    const target = (requested ? settingsSectionAlias(requested) : settingsSectionForHash(location.hash, ids)) || settingsLanding(ids);
    return <Navigate replace to={sectionHref(target)} />;
  }
  const section = sections.find(item => item.id === requested);
  const titles = Object.fromEntries(ids.map(id => [id, sections.find(item => item.id === id)?.title ?? id]));
  // Every editor keeps its own unsaved draft; leaving the page would drop it silently.
  const canLeave = () => !content.current?.querySelector("[data-settings-unsaved]")
    || window.confirm(t`You have unsaved changes. Leave this page?`);
  const shown: SettingsLayoutSection = section
    ? { ...section, description: section.description ?? settingsSectionHelp(section.id), rows: <div ref={content} className="min-w-0">
      <AreaConsoleLink section={section.id} allowedTabs={allowedTabs} tabHref={tabHref} />{section.rows as ReactNode}</div> }
    // A permission, module or async gate (e.g. hosting availability) hides it right now.
    : { id: requested, title: t`Settings`, rows: <EmptyState title={t`This settings page isn't available`}
      description={t`It may be switched off for this ${noun}, or your role can't open it.`}
      action={<Link className="desk-button-primary" to={sectionHref(settingsLanding(ids))}>{t`Go to settings overview`}</Link>} /> };
  return <>
    {/* Every editor owns its own query, so the parent GET never gates the page: while it
        loads the rows fall back to the `makerspace` prop (and disable via `loading`), and a
        failure is reported here instead of hiding payments, notifications and the rest. */}
    <SettingsLayout header={{ title: t`${nounTitle} settings`, subtitle: t`Make this space work for your community.`,
      meta: <>{settings.error ? <ErrorBlock className="w-full" onRetry={() => { void settings.refetch(); }}
        error={new Error(t`Couldn't load the latest settings (${settings.error.message}). Showing the last known values.`)} /> : null}</>,
      primary: { label: t`View public site`, href: `/m/${makerspace.slug}` } }}
      state={{ status: "ready" }}
      nav={<SettingsSectionNav titles={titles} links={links} active={requested} href={sectionHref} canLeave={canLeave} />}
      sections={[shown]} danger={canManageMakerspace && requested === "general" ? [{ title: t`Archive this ${noun}`,
        consequence: archivePending ? t`An archival request is pending superadmin review. Open it to see the request or withdraw it.`
          : t`Request archival for this makerspace. A superadmin must confirm before staff access is removed.`,
        action: { label: archivePending ? t`View pending request` : t`Request archival`, onClick: () => setArchiveOpen(true) } }] : []} />
    <Modal open={archiveOpen} onClose={() => setArchiveOpen(false)} title={t`Archive this ${noun}`} size="xl">
      <MakerspaceArchiveRequestPanel makerspaceId={makerspace.id} canManageMakerspace={canManageMakerspace} />
    </Modal>
  </>;
}
