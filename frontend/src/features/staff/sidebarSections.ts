import {
  Home, Inbox, ClipboardList, Hand, PackageCheck, Wallet, Boxes, Wrench, ClipboardCheck,
  ArrowLeftRight, ShoppingCart, Tags, Container, BookOpen, ShieldCheck, QrCode, ScanLine,
  Upload, Cog, Monitor, Users, Calendar, CalendarClock, CreditCard, ChartNoAxesCombined,
  ScrollText, CircleAlert, Building2, Network, Settings, Mail, KeyRound, Download,
  DatabaseBackup, Gauge, Puzzle, MoveRight, Globe, type LucideIcon,
} from "lucide-react";
import type { ShellItem, ShellSection } from "../../components/shell";
import { TAB_LABELS } from "./staffAccess";
import { staffTabPath } from "./staffTabs";

type Definition = { key: string; label?: string; caption?: string; tabs: string[]; more?: string[] };
export const SIDEBAR_SECTIONS: readonly Definition[] = [
  { key: "home", tabs: ["dashboard", "notifications"] },
  { key: "desk", label: "Front desk", tabs: ["requests", "direct", "handover", "payments"] },
  { key: "inventory", label: "Inventory", tabs: ["inventory", "ledger", "scanner", "needsfix", "stocktake", "transfers", "tobuy"], more: ["categories", "containers", "warranty", "qr", "bulk"] },
  { key: "machines", label: "Machines", tabs: ["machines", "devices"] },
  { key: "community", label: "Community", tabs: ["members", "events", "bookings"], more: ["cards"] },
  { key: "insights", label: "Insights", tabs: ["reports", "audit", "accountability"] },
  { key: "organizations", label: "Organizations", caption: "Across venues", tabs: ["organizations", "organized", "organization-analytics"] },
  { key: "settings", tabs: ["settings", "users", "emailtemplates", "email-logs", "api", "exports", "backups", "usage", "modules", "migration"] },
  { key: "platform", label: "Platform", tabs: ["platform-dashboard", "platform"] },
];
export const SIDEBAR_LABELS: Readonly<Record<string, string>> = {
  dashboard: "Home", notifications: "Inbox", handover: "Job pickups", inventory: "Items",
  needsfix: "Repair shelf", tobuy: "To buy", qr: "QR tools",
  "organization-analytics": "Org analytics", settings: "General", users: "Staff & roles", "email-logs": "Delivery log",
};
const ICONS: Record<string, LucideIcon> = {
  dashboard: Home, notifications: Inbox, requests: ClipboardList, direct: Hand, handover: PackageCheck,
  payments: Wallet, inventory: Boxes, needsfix: Wrench, stocktake: ClipboardCheck, transfers: ArrowLeftRight,
  tobuy: ShoppingCart, categories: Tags, containers: Container, ledger: BookOpen, warranty: ShieldCheck,
  qr: QrCode, scanner: ScanLine, bulk: Upload, machines: Cog, devices: Monitor, members: Users,
  events: Calendar, bookings: CalendarClock, cards: CreditCard, reports: ChartNoAxesCombined,
  audit: ScrollText, accountability: CircleAlert, organizations: Building2, organized: Calendar,
  "organization-analytics": Network, settings: Settings, users: Users, emailtemplates: Mail,
  "email-logs": Mail, api: KeyRound, exports: Download, backups: DatabaseBackup, usage: Gauge,
  modules: Puzzle, migration: MoveRight, "platform-dashboard": Globe, platform: Settings,
};

/** Presentation only: the caller supplies the already permission/module-filtered tab set. */
export function sidebarSections(moduleAllowedTabs: readonly string[], activeKey: string,
  path: (tab: string) => string = tab => staffTabPath(tab, false), onSelect?: (tab: string) => void,
  flat = false): ShellSection[] {
  const item = (key: string): ShellItem => ({ key, label: SIDEBAR_LABELS[key] ?? TAB_LABELS[key], href: path(key), icon: ICONS[key], onSelect: () => onSelect?.(key) });
  if (flat) return [{ key: "desk", items: ["requests", "direct", "handover", "payments", "notifications"].filter(key => moduleAllowedTabs.includes(key)).map(item) }];
  return SIDEBAR_SECTIONS.map(section => {
    const items = section.tabs.filter(key => moduleAllowedTabs.includes(key)).map(item);
    const more = section.more?.filter(key => moduleAllowedTabs.includes(key)).map(item);
    if (section.key === "settings" && items.length) {
      const familyOpen = items.some(child => child.key === activeKey);
      // Staff & roles is a daily destination, not a setting: keep it one click away even
      // while the Settings family is collapsed.
      const staff = !familyOpen && items[0].key !== "users" ? items.filter(child => child.key === "users") : [];
      return { key: section.key, items: [{
        key: "settings-family", label: "Settings", href: items[0].href, icon: Settings,
        onSelect: items[0].onSelect, children: familyOpen ? items : undefined,
      }, ...staff] };
    }
    return { key: section.key, label: section.label, caption: section.caption, items, more };
  }).filter(section => section.items.length || section.more?.length);
}
