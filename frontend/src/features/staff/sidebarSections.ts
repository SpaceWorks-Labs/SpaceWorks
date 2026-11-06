import { t } from "@lingui/core/macro";
import {
  Home, Inbox, ClipboardList, Hand, PackageCheck, Wallet, Boxes, Wrench, ClipboardCheck,
  ArrowLeftRight, ShoppingCart, Tags, Container, BookOpen, ShieldCheck, QrCode, ScanLine,
  Upload, Cog, Monitor, Users, Calendar, CalendarClock, CreditCard, ChartNoAxesCombined,
  ScrollText, CircleAlert, Building2, Network, Settings, Mail, KeyRound, Download,
  DatabaseBackup, Gauge, Puzzle, MoveRight, Globe, LayoutGrid, CalendarCheck, Undo2, Lock, Landmark, type LucideIcon,
  PackageMinus, HardHat,
  Store,
} from "lucide-react";
import type { ShellItem, ShellSection } from "../../components/shell";
import { TAB_LABELS } from "./staffAccess";
import { staffTabPath } from "./staffTabs";

type Definition = { key: string; label?: string; caption?: string; tabs: string[]; more?: string[] };
export const SIDEBAR_SECTIONS: readonly Definition[] = [
  { key: "home", tabs: ["dashboard", "notifications", "channels"] },
  { key: "desk", label: t`Front desk`, tabs: ["requests", "direct", "handover", "payments", "refunds", "finance"] },
  { key: "shop", label: t`Shop`, tabs: ["shop"] },
  { key: "inventory", label: t`Inventory`, tabs: ["inventory", "ledger", "scanner", "needsfix", "stocktake", "transfers", "tobuy", "consumables"], more: ["categories", "containers", "warranty", "qr", "bulk"] },
  { key: "machines", label: t`Machines`, tabs: ["machines", "devices", "repairs"] },
  { key: "community", label: t`Community`, tabs: ["members", "events", "bookings", "granted"], more: ["cards"] },
  { key: "insights", label: t`Insights`, tabs: ["reports", "analytics", "audit", "accountability"] },
  { key: "organizations", label: t`Organizations`, caption: t`Across venues`, tabs: ["organizations", "organized", "organization-analytics"] },
  { key: "settings", tabs: ["settings", "security", "users", "emailtemplates", "email-logs", "api", "exports", "backups", "usage", "modules", "migration"] },
  { key: "platform", label: t`Platform`, tabs: ["platform-dashboard", "platform-spaces", "platform", "platform-analytics"] },
];
export const SIDEBAR_LABELS: Readonly<Record<string, string>> = {
  dashboard: t`Home`, notifications: t`Inbox`, handover: t`Job pickups`, inventory: t`Items`,
  needsfix: t`Repair shelf`, tobuy: t`To buy`, qr: t`QR tools`,
  "organization-analytics": t`Org analytics`, settings: t`General`, users: t`Staff & roles`, "email-logs": t`Delivery log`,
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
  modules: Puzzle, migration: MoveRight, "platform-dashboard": Globe, "platform-spaces": LayoutGrid, platform: Settings,
  consumables: PackageMinus, repairs: HardHat, analytics: ChartNoAxesCombined, "platform-analytics": ChartNoAxesCombined,
  shop: Store,
};

/**
 * The Space Manager holds every action, so the generic grouping above handed them nine
 * long sections. Their menu is grouped by TASK instead (owner, 2026-10-16): what needs
 * doing today, people, each domain, money, then settings behind one collapsed family.
 * Less-used destinations sit under each group's "More". Nothing is dropped: every tab of
 * SIDEBAR_SECTIONS appears here as well (sidebarSections.test walks the old list).
 */
export const SPACE_MANAGER_SECTIONS: readonly Definition[] = [
  { key: "today", label: t`Today`, tabs: ["dashboard", "notifications", "channels", "requests", "direct", "handover"] },
  { key: "people", label: t`People`, tabs: ["users", "members", "cards"], more: ["organizations", "organization-analytics"] },
  { key: "inventory", label: t`Inventory & loans`, tabs: ["inventory", "accountability", "needsfix", "tobuy", "consumables", "scanner"],
    more: ["ledger", "stocktake", "transfers", "categories", "containers", "warranty", "qr", "bulk"] },
  { key: "machines", label: t`Machines`, tabs: ["machines", "devices", "repairs"] },
  { key: "events", label: t`Events`, tabs: ["events", "granted"], more: ["organized"] },
  { key: "bookings", label: t`Bookings`, tabs: ["bookings"] },
  { key: "shop", label: t`Shop`, tabs: ["shop"] },
  { key: "money", label: t`Money`, tabs: ["payments", "refunds", "finance", "reports", "analytics"] },
  { key: "settings", label: t`Space settings`, tabs: ["settings", "security", "emailtemplates", "email-logs", "api", "audit", "exports", "backups", "usage", "modules", "migration"] },
  { key: "platform", label: t`Platform`, tabs: ["platform-dashboard", "platform-spaces", "platform", "platform-analytics"] },
];
const SPACE_MANAGER_LABELS: Readonly<Record<string, string>> = { settings: t`Settings hub` };

/** Presentation only: the caller supplies the already permission/module-filtered tab set.
 *  `spaceManager` selects the task-grouped menu; every other role keeps SIDEBAR_SECTIONS. */
export function sidebarSections(moduleAllowedTabs: readonly string[], activeKey: string,
  path: (tab: string) => string = tab => staffTabPath(tab, false), onSelect?: (tab: string) => void,
  flat = false, spaceManager = false): ShellSection[] {
  const labels: Readonly<Record<string, string>> = spaceManager ? { ...SIDEBAR_LABELS, ...SPACE_MANAGER_LABELS } : SIDEBAR_LABELS;
  const item = (key: string): ShellItem => ({ key, label: labels[key] ?? TAB_LABELS[key], href: path(key), icon: ICONS[key], onSelect: () => onSelect?.(key) });
  if (flat) return [{ key: "desk", items: ["dashboard", "requests", "direct", "handover", "payments", "notifications", "channels", "granted"].filter(key => moduleAllowedTabs.includes(key)).map(item) }];
  return (spaceManager ? SPACE_MANAGER_SECTIONS : SIDEBAR_SECTIONS).map(section => {
    const items = section.tabs.filter(key => moduleAllowedTabs.includes(key)).map(item);
    const more = section.more?.filter(key => moduleAllowedTabs.includes(key)).map(item);
    if (section.key === "settings" && items.length) {
      const familyOpen = items.some(child => child.key === activeKey);
      // Staff & roles is a daily destination, not a setting: keep it one click away even
      // while the Settings family is collapsed (the Space Manager menu lists it under People).
      const staff = !familyOpen && items[0].key !== "users" ? items.filter(child => child.key === "users") : [];
      return { key: section.key, label: spaceManager ? section.label : undefined, items: [{
        key: "settings-family", label: t`Settings`, href: items[0].href, icon: Settings,
        onSelect: items[0].onSelect, children: familyOpen ? items : undefined,
      }, ...staff] };
    }
    return { key: section.key, label: section.label, caption: section.caption, items, more };
  }).filter(section => section.items.length || section.more?.length);
}
