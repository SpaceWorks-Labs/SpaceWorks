import { t } from "@lingui/core/macro";
import { toast, invalidateToastUndo } from "../../components/ui/toastStore";
import type { SettingsLayoutSection } from "../../components/layouts";
import { ApiClientsTelegramSettings } from "./ApiClientsTelegramSettings";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill, Field, SettingsRow } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { MakerspaceBrandingSettings } from "./MakerspaceBrandingSettings";
import { MakerspaceBookingRulesSettings } from "./MakerspaceBookingRulesSettings";
import { MakerspaceBookingSettings } from "./MakerspaceBookingSettings";
import { MakerspaceReminderSettings } from "./MakerspaceReminderSettings";
import { MakerspaceCustomDomainSettings } from "./MakerspaceCustomDomainSettings";
import { MakerspaceDirectoryVisibility } from "./MakerspaceDirectoryVisibility";
import { MakerspaceEmailSettings } from "./MakerspaceEmailSettings";
import { MakerspaceFilamentSettings } from "./MakerspaceFilamentSettings";
import { MakerspaceFeatureSettings } from "./MakerspaceFeatureSettings";
import { MakerspaceGeofenceSettings } from "./MakerspaceGeofenceSettings";
import { MakerspaceGeneralSettings } from "./MakerspaceGeneralSettings";
import { IntegrationHealthPanel } from "./IntegrationHealthPanel";
import { KioskStationSettings } from "./KioskStationSettings";
import { MakerspaceLocationSettings } from "./MakerspaceLocationSettings";
import { MakerspaceProfileSettings } from "./MakerspaceProfileSettings";
import { BillingDocumentsSettings } from "./BillingDocumentsSettings";
import { EventMoneySettings } from "./EventMoneySettings";
import { TaxSettings } from "../finance/TaxSettings";
import { FyReceiptsSetting } from "../finance/FyReceiptsSetting";
import { PricingSettings } from "./pricing/PricingSettings";
import { capabilityOn } from "../../lib/features";
import { SpacePacksPanel } from "./SpacePacksPanel";
import { MakerspaceMembershipSettings } from "./MakerspaceMembershipSettings";
import { MakerspacePaymentSettings } from "./MakerspacePaymentSettings";
import { MakerspacePublicStatsSettings } from "./MakerspacePublicStatsSettings";
import { PublicStatsSettingsPanel } from "../stats/settings/PublicStatsSettingsPanel";
import { MakerspaceSubdomainSettings } from "./MakerspaceSubdomainSettings";
import { MakerspaceWebhookSettings } from "./MakerspaceWebhookSettings";
import { EventDefaultsSettings } from "./EventDefaultsSettings";
import { BorrowRequestAccessSettings } from "./BorrowRequestAccessSettings";
import { NotificationTimingSettings } from "./NotificationTimingSettings";
import { NotificationDestinations } from "./NotificationDestinations";
import { SpaceChatTemplates } from "./SpaceChatTemplates";
import { EvidenceRetentionPanel } from "./EvidenceRetentionPanel";
import { NotificationMuteMatrix } from "./NotificationMuteMatrix";
import { NotificationRecipientPicker } from "./NotificationRecipientPicker";
import { type Makerspace } from "./StaffPanels";
import { MakerspaceLoanPolicySettings } from "./MakerspaceLoanPolicySettings";
import { LoanReservationPolicySettings } from "./LoanReservationPolicySettings";
import { ChannelSetupPanel } from "../notifications/ChannelSetupPanel";
import { PlatformCredentialsPanel } from "../notifications/PlatformCredentialsPanel";
import { ChannelDeliveryLog } from "../notifications/ChannelDeliveryLog";
import { PresencePrivacySettings } from "../presence/PresencePrivacySettings";
import { PublicPageBuilder } from "../publicPages/PublicPageBuilder";
import { useHostingAvailability } from "../hosting/hostingApi";
import { HostingInvitations } from "./HostingInvitations";
import { communitySettingsSections } from "../community/settings/communitySettingsSections";
import { unitsSettingsSections } from "./units/unitsSettingsSection";
import { joinRegisterSettingsSections } from "./membershipLifecycle/joinRegisterSettings";
import { WALLET_SWITCHES, walletSettingsSections } from "../walletCredentials/walletSettingsSection";
import { LegalPagesEditor } from "../legal/LegalPagesEditor";

type Input = { makerspace: Makerspace; settings?: Makerspace; loading: boolean; isSuperadmin: boolean; canManageMakerspace: boolean };

/**
 * Every section of Makerspace settings with its existing editors, moved out of the panel
 * unchanged when the page was split into routed subpages (0.12.0). The permission and
 * module gates (#183B: a section for a module that is off is absent, not empty) decide
 * which sections exist; `SETTINGS_GROUPS` only decides where each one sits in the nav.
 */
export function useMakerspaceSettingsSections({ makerspace, settings, loading, isSuperadmin, canManageMakerspace }: Input): SettingsLayoutSection[] {
  const queryClient = useQueryClient();
  const staffNotificationsEnabled =
    settings?.staff_notifications_enabled ?? makerspace.staff_notifications_enabled ?? true;
  const publicPrintStatusLookupPolicy =
    settings?.public_print_status_lookup_policy ?? makerspace.public_print_status_lookup_policy ?? "email_unverified";
  const enabledModules = settings?.enabled_modules ?? makerspace.enabled_modules ?? [];
  const hostingAvailable = useHostingAvailability(canManageMakerspace);

  const updateStaffNotifications = useMutation({
    mutationFn: (next: boolean) =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ staff_notifications_enabled: next }),
      }),
    onMutate: () => invalidateToastUndo(`settings-${makerspace.id}-updateStaffNotifications`),
    onSuccess: async (_data, next) => {
      await (() => {
      queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] });
      queryClient.invalidateQueries({ queryKey: ["makerspaces"] });
      queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
    })();
      toast((next ? t`Staff emails turned on.` : t`Staff emails turned off.`), { undoKey: `settings-${makerspace.id}-updateStaffNotifications`, undo: async () => {
        await ((next: boolean) =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ staff_notifications_enabled: next }),
      }))(!next);
        await (() => {
      queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] });
      queryClient.invalidateQueries({ queryKey: ["makerspaces"] });
      queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
    })();
      } });
    },
  });

  const updatePrintStatusLookupPolicy = useMutation({
    mutationFn: (next: Makerspace["public_print_status_lookup_policy"]) =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ public_print_status_lookup_policy: next }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] });
      queryClient.invalidateQueries({ queryKey: ["makerspaces"] });
      queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
    },
  });

  const notificationsDisabled = loading || updateStaffNotifications.isPending;
  const shared = { makerspace, settings, loading };
  const features = settings?.enabled_features ?? makerspace.enabled_features ?? [];
  const staffEmail = <SettingsRow label={t`Staff email notifications`} helper={t`Email this makerspace’s managers when hardware and print request statuses change.`}>
    <StatusPill label={staffNotificationsEnabled ? t`On` : t`Off`} tone={staffNotificationsEnabled ? "success" : "neutral"} />
    <label className="flex min-h-11 items-center gap-3 text-sm font-semibold">
      <input type="checkbox" checked={staffNotificationsEnabled} disabled={notificationsDisabled}
        onChange={event => updateStaffNotifications.mutate(event.target.checked)} />{t`Send staff emails`}</label>
    {updateStaffNotifications.error ? <p role="alert" className="text-sm text-danger">{updateStaffNotifications.error.message}</p> : null}
  </SettingsRow>;
  const printRecovery = <SettingsRow label={t`Public print status recovery`} helper={t`Choose how people recover a public print request when they lose their status link.`}>
    <div className="@container grid gap-3"><StatusPill label={statusLookupLabel(publicPrintStatusLookupPolicy)} tone={publicPrintStatusLookupPolicy === "token_only" ? "neutral" : "success"} />
      <Field label={t`Public print status lookup policy`}><select className="desk-input w-full" value={publicPrintStatusLookupPolicy}
        disabled={loading || updatePrintStatusLookupPolicy.isPending}
        onChange={event => updatePrintStatusLookupPolicy.mutate(event.target.value as Makerspace["public_print_status_lookup_policy"])}>
        <option value="token_only">{t`Token only`}</option><option value="email_unverified">{t`Email lookup`}</option>
      </select></Field>
      {updatePrintStatusLookupPolicy.error ? <p role="alert" className="text-sm text-danger">{updatePrintStatusLookupPolicy.error.message}</p> : null}
    </div>
  </SettingsRow>;
  return [
    // This makerspace's local Space Manager or the platform superadmin (#115) edits the page.
    ...(canManageMakerspace ? [{ id: "public-page", title: t`Public page`, rows: <PublicPageBuilder owner={{ kind: "makerspace", id: makerspace.id }} /> }] : []),
    { id: "general", title: t`Profile & location`, rows: <>
      <MakerspaceGeneralSettings {...shared} />
      <MakerspaceLocationSettings {...shared} />
      {canManageMakerspace ? <MakerspaceProfileSettings makerspaceId={makerspace.id} /> : null}
    </> },
    { id: "branding", title: t`Branding & public site`, rows: <>
      <MakerspaceBrandingSettings {...shared} />{enabledModules.includes("printing") || enabledModules.includes("machine_service") ? printRecovery : null}
      {settings?.platform_hosting === true ? <MakerspaceSubdomainSettings makerspace={makerspace} settings={settings} /> : null}
      <MakerspaceCustomDomainSettings {...shared} />
      {canManageMakerspace ? <MakerspaceDirectoryVisibility {...shared} /> : null}
    </> },
    // #170: Settings › Public stats. Only the Space Manager (or the superadmin) opens this page;
    // area managers reach their own public-stats widgets through each domain's settings dialog.
    { id: "public-stats", title: t`Public stats`, rows: <>
      <PublicStatsSettingsPanel key={makerspace.id} makerspaceId={makerspace.id} slug={makerspace.slug} />
      <MakerspacePublicStatsSettings {...shared} />
    </> },
    { id: "features", title: t`Features`, rows: <>
      <MakerspaceFeatureSettings {...shared} />
      {canManageMakerspace && features.includes("packs.import")
        ? <SpacePacksPanel key={makerspace.id} makerspaceId={makerspace.id} isSuperadmin={isSuperadmin} /> : null}
    </> },
    // #183B: lending settings follow the `loans.enabled` master, like the lending tabs.
    ...(capabilityOn(settings ?? makerspace, "loans.enabled") ? [{ id: "lending", title: t`Inventory`, rows: <>
      {canManageMakerspace && features.includes("loans.enabled") ? <BorrowRequestAccessSettings makerspaceId={makerspace.id} /> : null}
      {enabledModules.includes("request_workflow") ? <MakerspaceLoanPolicySettings makerspaceId={makerspace.id} enabledFeatures={features} enabledModules={enabledModules} canManageMakerspace={canManageMakerspace} /> : null}
      {enabledModules.includes("request_workflow") && ["loans.pickup_windows", "loans.reservations", "loans.waitlist"].some(key => features.includes(key)) ? <LoanReservationPolicySettings makerspaceId={makerspace.id} /> : null}
      <MakerspaceReminderSettings {...shared} />
      {canManageMakerspace && (settings?.enabled_features ?? []).includes("inventory.kiosk") ? <KioskStationSettings makerspace={makerspace} /> : null}
    </> }] : []),
    // #183B: a section for a module that is off is not shown at all, not shown empty.
    ...(enabledModules.includes("membership") || enabledModules.includes("presence") ? [{ id: "membership", title: t`Membership`, rows: <>
      {enabledModules.includes("membership") ? <MakerspaceMembershipSettings {...shared} /> : null}<MakerspaceGeofenceSettings {...shared} />
    </> }] : []),
    ...walletSettingsSections(settings ?? makerspace, canManageMakerspace), // ID-11
    // Decision 223: Settings › Guest passes and Settings › Community, each behind its capabilities.
    ...communitySettingsSections(settings ?? makerspace, canManageMakerspace),
    ...unitsSettingsSections(settings ?? makerspace, canManageMakerspace), // parity O-F1: Settings › People › Member units
    ...joinRegisterSettingsSections(settings ?? makerspace, canManageMakerspace), // parity O-F2: Settings › People › Joining
    ...(canManageMakerspace && enabledModules.includes("presence") ? [{ id: "presence", title: t`Presence privacy`,
      rows: <PresencePrivacySettings key={makerspace.id} makerspaceId={makerspace.id} slug={makerspace.slug} /> }] : []),
    ...(enabledModules.includes("bookings") ? [{ id: "bookings", title: t`Bookings`, rows: <>
      <MakerspaceBookingSettings {...shared} /><MakerspaceBookingRulesSettings makerspace={makerspace} />
    </> }] : []),
    ...(canManageMakerspace && enabledModules.includes("events") ? [{ id: "events", title: t`Events`,
      rows: <EventDefaultsSettings key={makerspace.id} makerspaceId={makerspace.id} /> }] : []),
    ...(enabledModules.includes("machines") || enabledModules.includes("printing")
      ? [{ id: "materials", title: t`Machines & materials`, rows: <MakerspaceFilamentSettings {...shared} /> }] : []),
    { id: "money", title: t`Payments & billing`, rows: <>
      <MakerspacePaymentSettings makerspace={settings ?? makerspace} />
      {canManageMakerspace ? <BillingDocumentsSettings key={makerspace.id} makerspaceId={makerspace.id} /> : null}
      {canManageMakerspace ? <FyReceiptsSetting key={`fy-receipts-${makerspace.id}`} makerspace={settings ?? makerspace} /> : null}
      {canManageMakerspace ? <TaxSettings key={`tax-${makerspace.id}`} makerspaceId={makerspace.id} /> : null}
      {canManageMakerspace && enabledModules.includes("events") ? <EventMoneySettings key={`event-money-${makerspace.id}`} makerspaceId={makerspace.id} /> : null}
    </> },
    ...(capabilityOn(settings ?? makerspace, "charges.pricing") ? [{ id: "pricing", title: t`Pricing`,
      rows: <PricingSettings key={makerspace.id} makerspace={settings ?? makerspace} /> }] : []),
    { id: "notifications", title: t`Notifications`, rows: <>{staffEmail}
      {canManageMakerspace && enabledModules.includes("notifications") ? <NotificationTimingSettings key={makerspace.id} makerspaceId={makerspace.id} /> : null}
      <NotificationMuteMatrix makerspaceId={makerspace.id} /><NotificationRecipientPicker makerspaceId={makerspace.id} />
      <NotificationDestinations availableChannels={enabledModules} makerspaceId={makerspace.id} />
      {canManageMakerspace ? <SpaceChatTemplates makerspace={makerspace} /> : null}
    </> },
    ...(canManageMakerspace ? [{ id: "channels", title: t`Communication channels`,
      description: t`Choose the mediums this space uses and set up their credentials. Staff and members can only pick channels you turn on here.`,
      rows: <><PlatformCredentialsPanel key={`platform:${makerspace.id}`} makerspaceId={makerspace.id} enabledModules={enabledModules}
        walletOn={WALLET_SWITCHES.some(key => capabilityOn(settings ?? makerspace, key))} />
        <ChannelSetupPanel key={makerspace.id} makerspaceId={makerspace.id} enabledModules={enabledModules} />
        <div className="py-4"><ChannelDeliveryLog key={makerspace.id} makerspaceId={makerspace.id} /></div></> }] : []),
    ...(canManageMakerspace && hostingAvailable ? [{ id: "hosting", title: t`Invite a makerspace`,
      rows: <div className="py-4"><HostingInvitations key={makerspace.id} scope={{ makerspaceId: makerspace.id }} /></div> }] : []),
    // Decision 255: email sending sits under Communication; webhooks and the bot under Integrations.
    ...(enabledModules.includes("email") ? [{ id: "email", title: t`Email sending`, rows: <MakerspaceEmailSettings makerspace={makerspace} /> }] : []),
    { id: "integrations", title: t`Webhooks`, rows: <>
      <MakerspaceWebhookSettings makerspace={makerspace} enabledModules={enabledModules} />
      {isSuperadmin && enabledModules.includes("telegram") ? <ApiClientsTelegramSettings makerspace={makerspace} /> : null}
    </> },
    { id: "health", title: t`Integration health`,
      rows: <IntegrationHealthPanel makerspace={makerspace} isSuperadmin={isSuperadmin} /> },
    ...(canManageMakerspace ? [{ id: "privacy", title: t`Privacy & evidence`,
      rows: <><EvidenceRetentionPanel makerspaceId={makerspace.id} />
        {capabilityOn(settings ?? makerspace, "legal.space_pages") ? <LegalPagesEditor scope={{ kind: "space", makerspaceId: makerspace.id }} /> : null}</> }] : []),
  ];
}

function statusLookupLabel(policy: Makerspace["public_print_status_lookup_policy"]) {
  return policy === "token_only" ? t`Token only` : t`Email lookup`;
}
