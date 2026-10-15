import { useState, type ReactNode } from "react";
import { skipToken, useQuery } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { Cog } from "lucide-react";
import { AppShell, JobTrayPill, type ShellWorkspace } from "../../components/shell";
import type { StaffAuthUser } from "../../lib/api";
import type { Makerspace } from "./panels/shared";
import { CommandPalette } from "./CommandPalette";
import { sidebarSections } from "./sidebarSections";
import { useUnreadNotifications } from "./useUnreadNotifications";
import { collectionResults, machineKeys, type MachineCollection, type MachineType } from "./machinesApi";
import { machineTypeSegment, staffTabPath } from "./staffTabs";

type Props = { activeMakerspace?: Makerspace; allowedTabs: readonly string[]; activeTab: string;
  guestOnly: boolean; singleTenantLocked: boolean; handoutOnly: boolean; user: StaffAuthUser;
  roleName?: string; isSuperadmin: boolean; makerspaces: Makerspace[]; setSelected: (id: number | null) => void;
  setTab: (tab: string) => void; signOut: () => Promise<void>; actions: readonly string[]; children: ReactNode };

export function StaffShell(props: Props) {
  const { activeMakerspace: space, allowedTabs, activeTab, guestOnly, singleTenantLocked, user } = props;
  const [paletteOpen, setPaletteOpen] = useState(false);
  const location = useLocation();
  const unread = useUnreadNotifications(space?.id, !!space && allowedTabs.includes("notifications"));
  // Subscribe to existing server-state caches; shell rendering must never issue dashboard/type requests.
  const dashboard = useQuery<{ pending_requests?: number; awaiting_issue?: number }>({
    queryKey: ["dashboard", space?.id], queryFn: skipToken, enabled: false,
  });
  const types = useQuery<MachineCollection<MachineType>>({ queryKey: machineKeys.types(space?.id ?? -1), queryFn: skipToken, enabled: false });
  const path = (tab: string, subPath = "") => staffTabPath(tab, guestOnly, space?.slug, singleTenantLocked, subPath);
  const tabs = space ? allowedTabs : allowedTabs.filter(key => ["organizations", "platform-dashboard"].includes(key));
  const nav = sidebarSections(tabs, activeTab, path, props.setTab, props.handoutOnly);
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
      const selectedType = item.children.find(child => child.href === location.pathname);
      if (selectedType) activeKey = selectedType.key;
    }
  }
  const publicPage = space ? [{ label: "View public page ↗", href: singleTenantLocked ? "/" : `/m/${space.slug}` }] : [];
  const menu = !singleTenantLocked ? [
    ...(props.makerspaces.length > 1 ? props.makerspaces.map(row => ({ label: row.name, onClick: () => props.setSelected(row.id) })) : []),
    ...(props.isSuperadmin ? [{ label: "Switch makerspace", onClick: () => props.setSelected(null) }] : []), ...publicPage,
  ] : [];
  const workspace: ShellWorkspace | undefined = space ? { name: space.name, subtitle: props.roleName ?? "",
    avatar: { kind: "avatar", name: space.name, seed: space.slug }, menu, locked: singleTenantLocked || props.makerspaces.length === 1 } : props.isSuperadmin ? {
      name: "Choose a space", subtitle: "Super Admin", avatar: { kind: "icon", icon: "Settings", tone: "neutral" },
      menu: props.makerspaces.map(row => ({ label: row.name, onClick: () => props.setSelected(row.id) })),
    } : undefined;
  return <>
    <AppShell variant="staff" workspace={workspace} nav={nav} activeKey={activeKey}
      compactNav={props.handoutOnly ? "bottom-tabs" : "drawer"} footerLinks={publicPage}
      search={space ? { label: "Search and commands", shortcut: "mod+k", onOpen: () => setPaletteOpen(true) } : undefined}
      status={space ? <JobTrayPill makerspaceId={space.id} /> : null}
      user={{ name: user.username, role: props.roleName, menu: [{ label: "Account & two-step sign-in", href: "/mfa" }, ...(!singleTenantLocked && props.isSuperadmin && props.makerspaces.length === 1 ? [{ label: "Switch makerspace", onClick: () => props.setSelected(null) }] : [])], onSignOut: () => void props.signOut() }}>
      {/* Below lg the sidebar (and its job pill) lives in the drawer, so running jobs surface here.
          Both pills share the job-status query keys, so this adds no polling. */}
      {space ? <div className="mb-4 empty:hidden lg:hidden"><JobTrayPill makerspaceId={space.id} /></div> : null}
      {props.children}
    </AppShell>
    {space ? <CommandPalette key={space.id} makerspaceId={space.id} makerspaceSlug={space.slug} allowedTabs={allowedTabs}
      guestOnly={guestOnly} singleTenantLocked={singleTenantLocked} ownerName={user.username} actions={props.actions}
      isSuperadmin={props.isSuperadmin} open={paletteOpen} onOpenChange={setPaletteOpen} /> : null}
  </>;
}
