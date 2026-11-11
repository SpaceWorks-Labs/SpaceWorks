import { t } from "@lingui/core/macro";
import type { Makerspace } from "./panels/shared";
import { settingsLinkTarget } from "./settingsSections";

export type HubTarget = { section: string } | { tab: string; view?: string };
export type HubEntry = { id: string; title: string; description: string; keywords: string; target: HubTarget };
type Meta = [title: string, description: string, keywords: string];

/**
 * One line of help per settings page (decision 255: every setting has a one-line
 * explanation and is searchable). Titles and help are translated when read, so a language
 * switch relabels them; the English keywords are extra search terms only, never shown.
 */
const SECTION_META = (): Record<string, Meta> => ({
  "public-page": [t`Public page`, t`Arrange the sections of your public page, claim a handle and publish it.`, "public page builder profile handle share qr gallery team story publish palette cover"],
  general: [t`Profile & location`, t`Name, address, opening hours and the public profile.`, "general name address location map profile description about opening hours"],
  branding: [t`Branding & public site`, t`Logo, colours, support email and your web address.`, "logo cover colour color theme brand public site subdomain custom domain print status lookup support email"],
  "public-stats": [t`Public stats`, t`The stats page: sections, order, period, headline numbers and TV mode.`, "public stats numbers page sections period headline tv kiosk screen lobby borrower names"],
  features: [t`Features`, t`Switch optional features inside each area on or off. Turning one off keeps its data.`, "feature switches toggles packs import options"],
  lending: [t`Inventory`, t`Loan period, renewals, borrow limits, who can request, reminders and kiosks.`, "inventory lending loan days default return window renewals self renewal renew own loans account borrowers borrow limits reminders kiosk station anonymous requests overdue escalation grace closed days"],
  membership: [t`Membership`, t`How people join, dues, wallet passes and the check-in area.`, "members join policy dues fee included hours plans referrals geofence check in presence gps location radius wallet passes"],
  units: [t`Member units`, t`Districts, chapters or branches inside the space, and staff limited to one unit.`, "units unit district chapter branch area state level levels hierarchy tree code join link unit scoped staff lead payment instructions"],
  "guest-passes": [t`Guest passes`, t`Guest borrowing, machine use, sponsors and day passes.`, "guest pass passes day pass visitor sponsor bring a guest walk in door registration waiver deposit liability on-site borrowing supervised machine use induction certification"],
  community: [t`Community`, t`Minors and guardian consent, volunteer credit and the join follow-up.`, "minors children under age guardian consent volunteer hours credit join follow up funnel"],
  presence: [t`Presence privacy`, t`Show names on the public display and let people hide their name.`, "presence privacy display names anonymous opt out hide me now screen"],
  bookings: [t`Bookings`, t`Booking rules, reminders and messages to the person who booked.`, "bookings rooms spaces rules reminders requester notifications"],
  events: [t`Events`, t`Default audience and reminders for new events.`, "events default audience registration reminders equipment return window venue room"],
  materials: [t`Machines & materials`, t`When to warn that filament and other materials run low.`, "machines materials filament low stock threshold 3d printing"],
  money: [t`Payments & billing`, t`Online checkout, invoices and receipts, tax and event money.`, "money payments stripe razorpay checkout invoices receipts billing documents fees tax"],
  pricing: [t`Pricing`, t`Free or paid per area, the rates, member discounts and the currency new charges use.`, "price pricing prices rates rental deposit late fee discount discounts member currency free paid"],
  notifications: [t`Notifications`, t`Staff alerts, delivery times, muting, recipients and chat rooms.`, "notifications staff email timing quiet hours mute recipients rooms destinations alerts"],
  channels: [t`Communication channels`, t`Email, Telegram, Slack, Mattermost, Discord, SMS, WhatsApp and app push.`, "channels medium telegram slack mattermost discord sms whatsapp twilio meta push email fallback credentials bot token templates test delivery log"],
  email: [t`Email sending`, t`The address and server this space sends email from.`, "email smtp sender from address reply to mail server"],
  integrations: [t`Webhooks`, t`Send signed event messages to other systems, and the Telegram bot.`, "webhooks integrations telegram api signed events callbacks zapier"],
  health: [t`Integration health`, t`Whether email, payments, chat and other connections are working.`, "health status diagnostics integrations checks errors"],
  hosting: [t`Invite a makerspace`, t`Invite another group to run its own makerspace on this server.`, "invite host another makerspace hosting request subdomain"],
  privacy: [t`Privacy & evidence`, t`How long handover and return photos are kept.`, "privacy evidence photos retention delete"],
});

/** Settings that live on their own console pages (or a console's settings view). */
const TAB_META = (): Record<string, Meta> => ({
  security: [t`Security`, t`Staff sign-in rules, account locks and platform access to personal data.`, "security mfa two-step authenticator totp sign in lock platform pii personal data privacy superadmin"],
  users: [t`Staff & roles`, t`Give people staff roles, invite them by email and choose the machine types they manage.`, "staff team people appoint roles users accounts invite machine manager event manager booking manager inventory manager handover"],
  emailtemplates: [t`Email templates`, t`Edit the wording of the emails this space sends.`, "email templates messages wording"],
  "email-logs": [t`Delivery log`, t`Every email and message sent, failed or skipped.`, "email log delivery failed bounced sent"],
  api: [t`API access`, t`Keys for other software that reads or writes this space's data.`, "api clients keys tokens integrations developers"],
  audit: [t`Audit log`, t`Who changed what, and when.`, "audit log history changes actions"],
  exports: [t`Data export`, t`Download your space's data.`, "export download data csv archive gdpr"],
  backups: [t`Backup & restore`, t`Backups of this space and restoring from one.`, "backup restore snapshot recovery"],
  usage: [t`Usage & limits`, t`How much of each limit this space uses: storage, members, emails and more.`, "usage limits storage quota plan allowance remaining members emails sms"],
  modules: [t`Areas & add-ons`, t`Turn whole areas such as Events, Bookings or the Shop, and add-ons like SMS, on or off.`, "modules areas add-ons install uninstall apps switch on off maintenance to-buy warranty"],
  migration: [t`Move to another server`, t`Move this space and its data to another SpaceWorks server.`, "migration move transfer tenant import export server"],
  stocktake: [t`Stocktake`, t`Count what is on the shelves and reconcile it with the records.`, "stocktake stock count shelf variance reconcile"],
  inventory: [t`Inventory settings`, t`Inventory switches and loan rules, from the Inventory page's settings menu.`, "inventory lending loans settings loan policy"],
  machines: [t`Machine settings`, t`Per machine type: jobs, sessions, materials and reminders, on the Machines page.`, "machines settings maintenance certification"],
  events: [t`Event settings`, t`Event switches, from the Events page's settings menu.`, "events settings features"],
  bookings: [t`Booking settings`, t`Booking switches and rules, from the Bookings page's settings menu.`, "bookings settings rules features"],
  "shop/settings": [t`Shop`, t`Holds, pickup reminders, returns window and the shop policy.`, "shop store sell merch kits policy pickup holds returns reminders cash till"],
  "donations/profile": [t`Non-profit and receipts`, t`Registration number, tax exemption and who signs donation receipts.`, "donations non-profit nonprofit charity 80g 12a 501c3 receipts signatory tax exempt"],
});

const sectionEntries = (): HubEntry[] => Object.entries(SECTION_META())
  .map(([id, [title, description, keywords]]) => ({ id, title, description, keywords, target: { section: id } }));

const tabEntries = (): HubEntry[] => Object.entries(TAB_META()).map(([key, [title, description, keywords]]) => {
  const [tab, view] = key.split("/");
  return { id: `tab:${key}`, title, description, keywords, target: view ? { tab, view } : { tab } };
});

/** The one-line help of a settings page, shown under its title. */
export function settingsSectionHelp(id: string): string | undefined {
  return SECTION_META()[id]?.[1];
}

/** The title and help of a `tab:<tab>[/<view>]` menu entry, or null if this build has none. */
export function settingsLinkEntry(item: string): HubEntry | null {
  return settingsLinkTarget(item) ? tabEntries().find(entry => entry.id === item) ?? null : null;
}

/** Every destination the hub can offer, narrowed to what this page shows and the actor may open. */
export function hubEntries(sectionIds: readonly string[], allowedTabs: readonly string[]): HubEntry[] {
  return [
    ...sectionEntries().filter(entry => sectionIds.includes(entry.id)),
    ...tabEntries().filter(entry => "tab" in entry.target && allowedTabs.includes(entry.target.tab)),
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
    { id: "location", label: t`Add your address`, done: Boolean(space.location?.trim()), target: { section: "general" } },
    { id: "logo", label: t`Upload your logo`, done: Boolean(space.logo_url), target: { section: "branding" } },
    { id: "support", label: t`Add a support email`, done: Boolean(space.branding_config?.support_email), target: { section: "branding" } },
    { id: "features", label: t`Turn on the features you use`, done: Boolean(space.enabled_features?.length), target: { section: "features" } },
    ...(options.channelsReady !== undefined
      ? [{ id: "channels", label: t`Choose how people get notified`, done: options.channelsReady, target: { section: "channels" } }] : []),
    ...(modules.includes("membership")
      ? [{ id: "geofence", label: t`Set the check-in area`, done: Boolean(space.geofence_enabled), target: { section: "membership" } }] : []),
  ];
}
