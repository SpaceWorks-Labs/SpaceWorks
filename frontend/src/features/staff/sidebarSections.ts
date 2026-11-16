import { t } from "@lingui/core/macro";
import {
  Home, Inbox, ClipboardList, Hand, PackageCheck, Wallet, Boxes, Wrench, ClipboardCheck,
  ArrowLeftRight, ShoppingCart, Tags, Container, BookOpen, ShieldCheck, QrCode, ScanLine,
  Upload, Cog, Monitor, Users, Calendar, CalendarClock, CreditCard, ChartNoAxesCombined,
  ScrollText, CircleAlert, Building2, Network, Settings, Mail, KeyRound, Download,
  DatabaseBackup, Gauge, Puzzle, MoveRight, Globe, LayoutGrid, CalendarCheck, Undo2, Lock, Landmark, type LucideIcon,
  PackageMinus, HardHat, UserCog, ShieldAlert, HardDrive,
  Store, TriangleAlert, CalendarDays, HandHeart, SlidersHorizontal,
} from "lucide-react";
import type { ShellItem, ShellSection } from "../../components/shell";
import { TAB_LABELS } from "./staffAccess";
import { staffTabPath } from "./staffTabs";

type Definition = { key: string; label?: string; caption?: string; tabs: string[]; more?: string[] };
// SA-4 (decision 285): the superadmin headings use the /control/ group names (platformSettingsGroups.ts).
// Inventory, Machines, Events, Bookings, Shop and Money have no platform-wide page, so they never appear here.
const PLATFORM_SECTIONS: readonly Definition[] = [
  { key: "platform:overview", label: t`Overview`, tabs: ["platform-dashboard"] },
  { key: "platform:spaces", label: t`Spaces`, tabs: ["platform-spaces"] },
  { key: "platform:people", label: t`People & roles`, tabs: ["platform-access"] },
  { key: "platform:messaging", label: t`Messaging & notifications`, tabs: ["platform-inbox"] },
  { key: "platform:integrations", label: t`Integrations & analytics`, tabs: ["platform-analytics"] },
  { key: "platform:limits", label: t`Limits & hosting`, tabs: ["platform-limits"] },
  { key: "platform:data", label: t`Data & recovery`, tabs: ["platform-data"] },
  { key: "platform:security", label: t`Security & audit`, tabs: ["platform-security"] },
  { key: "platform:settings", label: t`Platform settings`, tabs: ["platform"] },
];
export const SIDEBAR_SECTIONS: readonly Definition[] = [
  // The superadmin's platform pages come first: before a space is chosen they are the whole menu.
  // Decision 285: their order follows the /control/ groups (Overview, Spaces, People & roles, Messaging &
  // notifications, Integrations & analytics, Limits & hosting, Data & recovery, Security & audit), then settings.
  ...PLATFORM_SECTIONS,
  // "My channels" is a personal setting: it lives in the account menu (StaffShell), not here (0.12.0 row 10).
  { key: "home", tabs: ["dashboard", "schedule", "notifications", "incidents"] },
  // Role-screen audit 0.12.0: the counter's queues only. Money sat here too, so an Event,
  // Shop or Machine Manager got a "Front desk" heading holding nothing but money pages.
  { key: "desk", label: t`Front desk`, tabs: ["requests", "direct", "handover"] },
  { key: "shop", label: t`Shop`, tabs: ["shop"] },
  { key: "inventory", label: t`Inventory`, tabs: ["inventory", "ledger", "scanner", "needsfix", "stocktake", "transfers", "tobuy", "consumables"], more: ["categories", "containers", "warranty", "qr", "bulk"] },
  { key: "machines", label: t`Machines`, tabs: ["machines", "devices", "repairs"] },
  // The same Events / Bookings / People / Money headings the Space Manager's menu uses.
  { key: "events", label: t`Events`, tabs: ["events", "granted"] },
  { key: "bookings", label: t`Bookings`, tabs: ["bookings"] },
  { key: "people", label: t`People`, tabs: ["members", "cards"] },
  { key: "money", label: t`Money`, tabs: ["payments", "refunds", "finance", "donations"] },
  { key: "insights", label: t`Insights`, tabs: ["reports", "analytics", "audit", "accountability"] },
  { key: "organizations", label: t`Organizations`, caption: t`Across venues`, tabs: ["organizations", "organized", "organization-analytics"] },
  { key: "settings", tabs: ["settings", "security", "users", "emailtemplates", "email-logs", "api", "exports", "backups", "usage", "modules", "migration"] },
];
export const SIDEBAR_LABELS: Readonly<Record<string, string>> = {
  dashboard: t`Home`, notifications: t`Inbox`, handover: t`Pickups (Handover)`, inventory: t`Items`,
  needsfix: t`Repair shelf`, tobuy: t`To buy`, qr: t`QR tools`,
  "organization-analytics": t`Org analytics`, settings: t`All settings`, users: t`Staff & roles`, "email-logs": t`Delivery log`,
};
const ICONS: Record<string, LucideIcon> = {
  dashboard: Home, notifications: Inbox, channels: Settings, requests: ClipboardList, direct: Hand, handover: PackageCheck,
  payments: Wallet, refunds: Undo2, finance: Landmark, inventory: Boxes, needsfix: Wrench, stocktake: ClipboardCheck, transfers: ArrowLeftRight,
  tobuy: ShoppingCart, categories: Tags, containers: Container, ledger: BookOpen, warranty: ShieldCheck,
  qr: QrCode, scanner: ScanLine, bulk: Upload, machines: Cog, devices: Monitor, members: Users,
  events: Calendar, bookings: CalendarClock, cards: CreditCard, reports: ChartNoAxesCombined,
  audit: ScrollText, accountability: CircleAlert, organizations: Building2, organized: Calendar, granted: CalendarCheck,
  "organization-analytics": Network, settings: Settings, security: Lock, users: Users, emailtemplates: Mail,
  "email-logs": Mail, api: KeyRound, exports: Download, backups: DatabaseBackup, usage: Gauge,
  modules: Puzzle, migration: MoveRight, "platform-dashboard": Globe, "platform-spaces": LayoutGrid, "platform-inbox": Inbox, platform: Settings,
  "platform-access": UserCog, "platform-security": ShieldAlert, "platform-data": HardDrive, "platform-limits": SlidersHorizontal,
  consumables: PackageMinus, repairs: HardHat, analytics: ChartNoAxesCombined, "platform-analytics": ChartNoAxesCombined,
  shop: Store, incidents: TriangleAlert, schedule: CalendarDays,
  // The donations screens shipped without a sidebar icon, which crashed every full-access menu.
  donations: HandHeart,
};

/**
 * The Space Manager holds every action, so the generic grouping above handed them nine
 * long sections. Their menu is grouped by TASK instead (owner, 2026-10-16): what needs
 * doing today, people, each domain, money, then settings behind one collapsed family.
 * Less-used destinations sit under each group's "More". Nothing is dropped: every tab of
 * SIDEBAR_SECTIONS appears here as well (sidebarSections.test walks the old list).
 */
export const SPACE_MANAGER_SECTIONS: readonly Definition[] = [
  { key: "today", label: t`Today`, tabs: ["dashboard", "schedule", "notifications", "requests", "direct", "handover", "incidents"] },
  { key: "people", label: t`People`, tabs: ["users", "members", "cards"], more: ["organizations", "organization-analytics"] },
  { key: "inventory", label: t`Inventory & loans`, tabs: ["inventory", "accountability", "needsfix", "tobuy", "consumables", "scanner"],
    more: ["ledger", "stocktake", "transfers", "categories", "containers", "warranty", "qr", "bulk"] },
  { key: "machines", label: t`Machines`, tabs: ["machines", "devices", "repairs"] },
  { key: "events", label: t`Events`, tabs: ["events", "granted"], more: ["organized"] },
  { key: "bookings", label: t`Bookings`, tabs: ["bookings"] },
  { key: "shop", label: t`Shop`, tabs: ["shop"] },
  { key: "money", label: t`Money`, tabs: ["payments", "refunds", "finance", "donations"] },
  // Role-screen audit 0.12.0: reports cover every area and the audit log is not a setting,
  // so both sit under Insights, the heading every other role already sees them under.
  { key: "insights", label: t`Insights`, tabs: ["reports", "analytics", "audit"] },
  { key: "settings", label: t`Space settings`, tabs: ["settings", "security", "emailtemplates", "email-logs", "api", "exports", "backups", "usage", "modules", "migration"] },
  ...PLATFORM_SECTIONS,
];
const SPACE_MANAGER_LABELS: Readonly<Record<string, string>> = {};

// Role-screen audit 0.12.0: Repairs, To buy, Consumables and Warranties serve several areas
// and the server narrows their rows to the actor's area. In the generic menu each one sits
// with the first area the actor actually runs (the section holding that anchor tab), so a
// Booking Manager finds room repairs under Bookings, an Inventory Manager item repairs under
// Inventory, and nobody gets an "Inventory" or "Machines" heading for an area they do not
// manage. A Technician, who runs none of the anchors, gets a Maintenance heading.
const SHARED_HOMES: Readonly<Record<string, readonly string[]>> = {
  repairs: ["machines", "inventory", "bookings"], tobuy: ["inventory", "machines"],
  consumables: ["inventory", "machines"], warranty: ["inventory", "machines"],
};
const ANCHOR_TAB: Readonly<Record<string, string>> = { inventory: "inventory", machines: "machines", bookings: "bookings" };

function placeSharedTabs(allowed: readonly string[]): Definition[] {
  const shared = Object.keys(SHARED_HOMES);
  const sections: Definition[] = SIDEBAR_SECTIONS.map(section => ({ ...section,
    tabs: section.tabs.filter(tab => !shared.includes(tab)), more: section.more?.filter(tab => !shared.includes(tab)) }));
  const maintenance: Definition = { key: "maintenance", label: t`Maintenance`, tabs: [] };
  sections.splice(sections.findIndex(section => section.key === "insights"), 0, maintenance);
  for (const tab of shared) {
    const home = SHARED_HOMES[tab].find(key => allowed.includes(ANCHOR_TAB[key])) ?? "maintenance";
    const target = sections.find(section => section.key === home)!;
    if (tab === "warranty" && home === "inventory") target.more = [...target.more ?? [], tab];
    else target.tabs = [...target.tabs, tab];
  }
  return sections;
}

/** Presentation only: the caller supplies the already permission/module-filtered tab set.
 *  `spaceManager` selects the task-grouped menu; every other role keeps SIDEBAR_SECTIONS. */
export function sidebarSections(moduleAllowedTabs: readonly string[], activeKey: string,
  path: (tab: string) => string = tab => staffTabPath(tab, false), onSelect?: (tab: string) => void,
  flat = false, spaceManager = false): ShellSection[] {
  const labels: Readonly<Record<string, string>> = spaceManager ? { ...SIDEBAR_LABELS, ...SPACE_MANAGER_LABELS } : SIDEBAR_LABELS;
  const item = (key: string): ShellItem => ({ key, label: labels[key] ?? TAB_LABELS[key], href: path(key), icon: ICONS[key], onSelect: () => onSelect?.(key) });
  if (flat) return [{ key: "desk", items: ["dashboard", "requests", "direct", "handover", "payments", "notifications", "ledger", "granted"].filter(key => moduleAllowedTabs.includes(key)).map(item) }];
  return (spaceManager ? SPACE_MANAGER_SECTIONS : placeSharedTabs(moduleAllowedTabs)).map(section => {
    const items = section.tabs.filter(key => moduleAllowedTabs.includes(key)).map(item);
    const more = section.more?.filter(key => moduleAllowedTabs.includes(key)).map(item);
    // An area manager's "settings" pages are only Email templates and the API-access
    // request: a collapsed "Settings" button that opens one of those reads as space
    // settings they do not have, so without Settings or Security the pages sit flat.
    if (section.key === "settings" && items.some(child => child.key === "settings" || child.key === "security")) {
      const familyOpen = items.some(child => child.key === activeKey);
      // Staff & roles is a daily destination, not a setting: keep it one click away even
      // while the Settings family is collapsed (the Space Manager menu lists it under People).
      const staff = !familyOpen && items[0].key !== "users" ? items.filter(child => child.key === "users") : [];
      return { key: section.key, label: spaceManager ? section.label : undefined, items: [{
        key: "settings-family", label: t`Settings`, href: items[0].href, icon: Settings,
        onSelect: items[0].onSelect, children: familyOpen ? items : undefined,
      }, ...staff] };
    }
    const label = section.key === "settings" && !spaceManager ? t`Tools` : section.label;
    return { key: section.key, label, caption: section.caption, items, more };
  }).filter(section => section.items.length || section.more?.length);
}
