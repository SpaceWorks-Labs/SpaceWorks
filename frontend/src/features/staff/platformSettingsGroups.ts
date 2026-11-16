import { t } from "@lingui/core/macro";
import { consoleSessionHref } from "../../lib/api/sessionContext";
import type { SettingsGroup } from "./settingsSections";

/**
 * Platform settings use the /control/ admin's groups, in its order and with its names (decision 285):
 * Overview, Spaces, People & roles, Inventory, Machines, Events, Bookings, Shop, Money, Messaging & notifications,
 * Integrations & analytics, Limits & hosting, Data & recovery, Security & audit. A group with nothing
 * platform-wide to set (Inventory … Shop are configured per space) has no items, so the menu omits it.
 * `tab:` entries open the platform pages that hold the rest.
 */
export const platformSettingsGroups = (): readonly SettingsGroup[] => [
  { key: "overview", label: t`Overview`, items: ["tab:platform-dashboard"] },
  { key: "spaces", label: t`Spaces`, items: ["tab:platform-spaces", "tab:organization-reviews", "feature-defaults"] },
  { key: "people", label: t`People & roles`, items: ["sign-in", "sso", "tab:platform-access"] },
  { key: "inventory", label: t`Inventory`, items: [] },
  { key: "machines", label: t`Machines`, items: [] },
  { key: "events", label: t`Events`, items: [] },
  { key: "bookings", label: t`Bookings`, items: [] },
  { key: "shop", label: t`Shop`, items: [] },
  { key: "money", label: t`Money`, items: ["stripe"] },
  { key: "messaging", label: t`Messaging & notifications`, items: ["email", "providers", "chat-templates", "tab:platform-inbox"] },
  { key: "integrations", label: t`Integrations & analytics`, items: ["mobile-apps", "wallet", "eraser", "tab:platform-analytics"] },
  { key: "limits", label: t`Limits & hosting`, items: ["tab:platform-limits", "tab:hosting-plans", "tab:hosting-invoices", "deployment"] },
  { key: "data", label: t`Data & recovery`, items: ["tab:platform-data"] },
  { key: "security", label: t`Security & audit`, items: ["tab:platform-security", "legal"] },
];

/** The platform pages the menu links to, with their title and one line of help. */
export function platformSettingsLinks(): Record<string, { title: string; href: string; help: string }> {
  const href = (path: string) => consoleSessionHref(path, "platform");
  return {
    "tab:platform-dashboard": { title: t`Platform dashboard`, href: href("/admin/platform-dashboard"),
      help: t`What needs attention across every space.` },
    "tab:platform-spaces": { title: t`Spaces`, href: href("/admin/platform-spaces"),
      help: t`Every space's health and lifecycle, onboarding, requests and announcements.` },
    "tab:organization-reviews": { title: t`Organization reviews`, href: href("/admin/platform-spaces#organization-reviews"),
      help: t`Approve, decline or ask for changes to new organizations; suspend or reactivate others.` },
    "tab:platform-access": { title: t`People & roles`, href: href("/admin/platform-access"),
      help: t`Accounts, staff and Space Managers across every space.` },
    "tab:platform-inbox": { title: t`Inbox across spaces`, href: href("/admin/platform-inbox"),
      help: t`Unread notices and messages in every space.` },
    "tab:platform-analytics": { title: t`Platform analytics`, href: href("/admin/platform-analytics"),
      help: t`Dashboards across every space.` },
    "tab:platform-limits": { title: t`Per-space limits`, href: href("/admin/platform-limits"),
      help: t`Each space's limits (one at a time or in bulk), hosting other makerspaces and request rates.` },
    "tab:hosting-plans": { title: t`Hosting plans`, href: href("/admin/platform-spaces#plans"),
      help: t`The plans hosted spaces run under, on the Spaces page.` },
    "tab:hosting-invoices": { title: t`Hosting invoices`, href: href("/admin/platform-spaces#billing"),
      help: t`Invoices for hosted spaces and how they are paid, on the Spaces page.` },
    "tab:platform-data": { title: t`Data & recovery`, href: href("/admin/platform-data"),
      help: t`Backups, offsite copies, restore drills and moving spaces between servers.` },
    "tab:platform-security": { title: t`Security & audit`, href: href("/admin/platform-security"),
      help: t`IP rules, sign-in blocks, security locks for each space and the audit log.` },
  };
}
