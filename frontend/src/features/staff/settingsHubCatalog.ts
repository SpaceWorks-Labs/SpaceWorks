import type { Makerspace } from "./panels/shared";

export type HubTarget = { section: string } | { tab: string };
export type HubEntry = { id: string; title: string; description: string; keywords: string; target: HubTarget };

/** Sections of the Makerspace settings page, by the `id` MakerspaceSettingsPanel gives them. */
const SECTION_ENTRIES: HubEntry[] = [
  ["public-page", "Public page", "Arrange sections, claim a handle and publish your page.", "public page builder profile handle share qr gallery team story publish palette cover"],
  ["general", "General", "Name, address and public profile.", "name address location map profile description about"],
  ["branding", "Branding & public site", "Logo, colours, public stats and your web address.", "logo cover colour color theme brand public site stats subdomain custom domain print status lookup"],
  ["features", "Features", "Switch optional features on or off.", "feature switches toggles packs import capabilities"],
  ["lending", "Lending & loan policy", "Loan period, renewals, borrow limits and reminders.", "loan days default return window renewals borrow limits reminders kiosk station anonymous requests overdue escalation"],
  ["membership", "Membership", "Joining policy, dues and the check-in area.", "members join policy dues fee referrals geofence check in presence gps location radius"],
  ["presence", "Presence privacy", "Show names on the public display and let people hide their name.", "presence privacy display names anonymous opt out hide me now screen"],
  ["bookings", "Bookings", "Booking rules and requester messages.", "bookings rooms spaces rules reminders requester notifications"],
  ["events", "Events", "Default audience and reminders for new events.", "events default audience registration reminders"],
  ["materials", "Machines & materials", "Low-stock threshold for filament.", "machines materials filament low stock threshold 3d printing"],
  ["money", "Money", "Payments, online checkout and billing documents.", "money payments stripe razorpay checkout invoices receipts billing documents fees"],
  ["notifications", "Notifications", "Staff alerts, timing, muting, recipients and rooms.", "notifications staff email timing quiet hours mute recipients rooms destinations alerts"],
  ["channels", "Communication channels", "Email, Telegram, Slack, Mattermost, Discord, SMS, WhatsApp and app push.", "channels medium telegram slack mattermost discord sms whatsapp twilio meta push email fallback credentials bot token templates test delivery log"],
  ["integrations", "Email & integrations", "Outgoing email, webhooks and integration health.", "email smtp sender webhooks integrations health telegram api"],
  ["privacy", "Privacy & evidence", "Evidence photo retention.", "privacy evidence photos retention delete"],
].map(([id, title, description, keywords]) => ({ id, title, description, keywords, target: { section: id } }));

/** Settings that live on their own pages (or in a domain console's settings dialog). */
const TAB_ENTRIES: HubEntry[] = [
  ["security", "Security", "Staff sign-in rules, platform locks and platform access to personal data.", "security mfa two-step authenticator totp sign in lock platform pii personal data privacy superadmin"],
  ["users", "Staff & roles", "Create staff accounts, assign roles and machine types.", "staff team people appoint roles users accounts invite machine manager event manager booking manager inventory manager handover"],
  ["emailtemplates", "Email templates", "Edit the emails this space sends.", "email templates messages wording"],
  ["email-logs", "Email delivery log", "Every email sent, failed or skipped.", "email log delivery failed bounced sent"],
  ["api", "API access", "API clients and keys.", "api clients keys tokens integrations developers"],
  ["audit", "Audit log", "Who changed what, and when.", "audit log history changes actions"],
  ["exports", "Data export", "Export your space's data.", "export download data csv archive gdpr"],
  ["backups", "Backup & restore", "Backups of this space.", "backup restore snapshot recovery"],
  ["usage", "Usage & limits", "Storage and plan limits.", "usage limits storage quota plan"],
  ["modules", "Modules", "Switch modules on or off for this space.", "modules install uninstall apps switch on off maintenance to-buy warranty"],
  ["migration", "Tenant migration", "Move this space to another deployment.", "migration move tenant import export"],
  ["inventory", "Inventory settings", "Lending features and loan policy, from the Inventory page's settings menu.", "inventory lending loans settings loan policy"],
  ["machines", "Machine settings", "Machine features, from the Machines page.", "machines settings maintenance certification"],
  ["events", "Event settings", "Event features, from the Events page's settings menu.", "events settings features"],
  ["bookings", "Booking settings", "Booking features and rules, from the Bookings page's settings menu.", "bookings settings rules features"],
].map(([id, title, description, keywords]) => ({ id: `tab:${id}`, title, description, keywords, target: { tab: id } }));

/** Every destination the hub can offer, narrowed to what this page shows and the actor may open. */
export function hubEntries(sectionIds: readonly string[], allowedTabs: readonly string[]): HubEntry[] {
  return [
    ...SECTION_ENTRIES.filter(entry => sectionIds.includes(entry.id)),
    ...TAB_ENTRIES.filter(entry => "tab" in entry.target && allowedTabs.includes(entry.target.tab)),
  ];
}

/** Every word of the query must appear in the title, description or keywords. */
export function searchHub(entries: readonly HubEntry[], query: string): HubEntry[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  return entries.filter(entry => {
    const text = `${entry.title} ${entry.description} ${entry.keywords}`.toLowerCase();
    return words.every(word => text.includes(word));
  });
}

export type ChecklistItem = { id: string; label: string; done: boolean; target: HubTarget };

/** The first-run setup steps, each tied to the setting that completes it. */
export function setupChecklist(space: Makerspace, options: { channelsReady?: boolean } = {}): ChecklistItem[] {
  const modules = space.enabled_modules ?? [];
  return [
    { id: "location", label: "Add your address", done: Boolean(space.location?.trim()), target: { section: "general" } },
    { id: "logo", label: "Upload your logo", done: Boolean(space.logo_url), target: { section: "branding" } },
    { id: "support", label: "Add a support email", done: Boolean(space.branding_config?.support_email), target: { section: "branding" } },
    { id: "features", label: "Turn on the features you use", done: Boolean(space.enabled_features?.length), target: { section: "features" } },
    ...(options.channelsReady !== undefined
      ? [{ id: "channels", label: "Choose how people get notified", done: options.channelsReady, target: { section: "channels" } }] : []),
    ...(modules.includes("membership")
      ? [{ id: "geofence", label: "Set the check-in area", done: Boolean(space.geofence_enabled), target: { section: "membership" } }] : []),
  ];
}
