import { consoleSessionHref, currentSessionContext } from "../../lib/api/sessionContext";
import { useEffect, useState, type ReactNode } from "react";
import { setDelightSpaceFeatures } from "../../components/delight/spaceDelight";
import { skipToken, useQuery } from "@tanstack/react-query";
import { Navigate, useLocation } from "react-router-dom";
import { Cog } from "lucide-react";
import { AppShell, JobTrayPill, type ShellWorkspace } from "../../components/shell";
import type { StaffAuthUser } from "../../lib/api";
import type { Makerspace } from "./panels/shared";
import { CommandPalette } from "./CommandPalette";
import { sidebarSections } from "./sidebarSections";
import { useUnreadNotifications } from "./useUnreadNotifications";
import { collectionResults, machineKeys, type MachineCollection, type MachineType } from "./machinesApi";
import { machineTypeSegment, staffTabPath } from "./staffTabs";
import { visibleRequestTabs } from "./panels/requestTabs";

type Props = { activeMakerspace?: Makerspace; allowedTabs: readonly string[]; activeTab: string;
  guestOnly: boolean; singleTenantLocked: boolean; handoutOnly: boolean; grantOnly?: boolean; user: StaffAuthUser;
  roleName?: string; isSuperadmin: boolean; makerspaces: Makerspace[]; setSelected: (id: number | null) => void;
  setTab: (tab: string) => void; signOut: () => Promise<void>; actions: readonly string[]; children: ReactNode };

export function StaffShell(props: Props) {
  const { activeMakerspace: space, allowedTabs, activeTab, guestOnly, singleTenantLocked, user } = props;
  const [paletteOpen, setPaletteOpen] = useState(false);
  const location = useLocation();
  const unread = useUnreadNotifications(space?.id, !!space && allowedTabs.includes("notifications"));
  // The console has no tenant bootstrap: publish the active space's delight switches.
  const spaceFeatures = space?.enabled_features ?? null;
  useEffect(() => {
    setDelightSpaceFeatures(spaceFeatures);
    return () => setDelightSpaceFeatures(null);
  }, [spaceFeatures]);
  // Subscribe to existing server-state caches; shell rendering must never issue dashboard/type requests.
  const dashboard = useQuery<{ pending_requests?: number; awaiting_issue?: number }>({
    queryKey: ["dashboard", space?.id], queryFn: skipToken, enabled: false,
  });
  const types = useQuery<MachineCollection<MachineType>>({ queryKey: machineKeys.types(space?.id ?? -1), queryFn: skipToken, enabled: false });
  const path = (tab: string, subPath = "") => consoleSessionHref(staffTabPath(tab, guestOnly, props.isSuperadmin ? undefined : space?.slug, singleTenantLocked, subPath), props.isSuperadmin ? "platform" : currentSessionContext());
  // `requests` passes the tab gate for any hardware action, but each queue needs accept_request or
  // issue_request. With neither, the page would be a dead end: hide it and open the front desk instead.
  const noQueues = !visibleRequestTabs(guestOnly || props.handoutOnly, props.actions, props.isSuperadmin).length;
  const redirectTab = ["direct", "handover"].find(key => allowedTabs.includes(key));
  // "granted" (Assigned resources) is a global tab: event/booking grant holders reach it with no workspace selected.
  const tabs = space ? allowedTabs.filter(key => key !== "requests" || !noQueues || !redirectTab)
    : allowedTabs.filter(key => ["organizations", "platform-dashboard", "granted"].includes(key));
  // Full-access staff (Space Manager, superadmin) get the task-grouped menu; narrower roles
  // keep their existing, already short one.
  const spaceManager = !!space && (props.isSuperadmin || props.actions.includes("manage_makerspace"));
  const nav = sidebarSections(tabs, activeTab, path, props.setTab, props.handoutOnly, spaceManager);
  let activeKey = activeTab;
  for (const section of nav) for (const item of [...section.items, ...section.more ?? []]) {
    if (item.key === "notifications") { item.badge = unread; item.badgeLabel = "unread"; }
    if (item.key === "requests" && allowedTabs.includes("dashboard") && dashboard.isSuccess) {
      item.badge = (dashboard.data.pending_requests ?? 0) + (dashboard.data.awaiting_issue ?? 0);
    }
    if (item.key === "machines" && activeTab === "machines") {
      const rows = collectionResults(types.data);
      item.children = rows.slice(0, 8).map(type => ({ key: `machines:${type.id}`, label: type.name,
        href: path("machines", machineTypeSegment(type)), icon: Cog, onSelect: () => props.setTab("machines") }));
      if (rows.length > 8) item.children.push({ key: "machines:all", label: "All types →", href: path("machines"), icon: Cog });
      const selectedType = item.children.find(child => child.href?.split("?")[0] === location.pathname);
      if (selectedType) activeKey = selectedType.key;
    }
  }
  const publicPage = space ? [{ label: "View public page ↗", href: singleTenantLocked ? "/" : `/m/${space.slug}` }] : [];
  const menu = !singleTenantLocked ? [
    ...(props.makerspaces.length > 1 ? props.makerspaces.map(row => ({ label: row.name, onClick: () => props.setSelected(row.id) })) : []),
    ...(props.isSuperadmin ? [{ label: "Switch makerspace", onClick: () => props.setSelected(null) }] : []), ...publicPage,
  ] : [];
  const hasGrants = Boolean(user.event_grants?.length || user.booking_grants?.length);
  // A grant-only console (event/booking grants, no makerspace actions) has no makerspace-wide
  // search, commands or job tray: those read makerspace-scoped data the account cannot see.
  const makerspaceTools = !!space && !props.grantOnly;
  const workspace: ShellWorkspace | undefined = space ? { name: space.name, subtitle: [space.public_code || space.slug, props.roleName].filter(Boolean).join(" · "),
    avatar: { kind: "avatar", name: space.name, seed: space.slug }, menu, locked: singleTenantLocked || props.makerspaces.length === 1 } : props.isSuperadmin ? {
      name: "Choose a space", subtitle: "Super Admin", avatar: { kind: "icon", icon: "Settings", tone: "neutral" },
      menu: props.makerspaces.map(row => ({ label: row.name, onClick: () => props.setSelected(row.id) })),
    } : hasGrants ? { name: "Assigned resources", subtitle: "Resource staff", avatar: { kind: "icon", icon: "Calendar", tone: "neutral" }, menu: [], locked: true }
    : undefined;
  if (space && activeTab === "requests" && noQueues && redirectTab) return <Navigate replace to={path(redirectTab)} />;
  return <>
    <AppShell variant="staff" workspace={workspace} nav={nav} activeKey={activeKey}
      compactNav={props.handoutOnly ? "bottom-tabs" : "drawer"} footerLinks={publicPage}
      search={makerspaceTools ? { label: "Search and commands", shortcut: "mod+k", onOpen: () => setPaletteOpen(true) } : undefined}
      status={makerspaceTools ? <JobTrayPill makerspaceId={space.id} /> : null}
      user={{ name: user.username, role: props.roleName, menu: [{ label: "Account & two-step sign-in", href: `/mfa?context=${encodeURIComponent(currentSessionContext())}` }, ...(!singleTenantLocked && props.isSuperadmin && props.makerspaces.length === 1 ? [{ label: "Switch makerspace", onClick: () => props.setSelected(null) }] : [])], onSignOut: () => void props.signOut() }}>
      {/* Below lg the sidebar (and its job pill) lives in the drawer, so running jobs surface here.
          Both pills share the job-status query keys, so this adds no polling. */}
      {makerspaceTools ? <div className="mb-4 empty:hidden lg:hidden"><JobTrayPill makerspaceId={space.id} /></div> : null}
      {props.children}
    </AppShell>
    {makerspaceTools && space ? <CommandPalette key={space.id} makerspaceId={space.id} makerspaceSlug={space.slug} allowedTabs={allowedTabs}
      guestOnly={guestOnly} singleTenantLocked={singleTenantLocked} ownerName={user.username} actions={props.actions}
      isSuperadmin={props.isSuperadmin} open={paletteOpen} onOpenChange={setPaletteOpen} /> : null}
  </>;
}
