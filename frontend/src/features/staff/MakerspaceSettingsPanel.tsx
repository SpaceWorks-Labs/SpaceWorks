import { t } from "@lingui/core/macro";
import { consoleSessionHref } from "../../lib/api/sessionContext";
import { toast, invalidateToastUndo } from "../../components/ui/toastStore";
import { useState } from "react";
import { SettingsLayout, type SettingsLayoutSection } from "../../components/layouts";
import { ApiClientsTelegramSettings } from "./ApiClientsTelegramSettings";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { MakerspaceArchiveRequest } from "../../generated/api";

import { ErrorBlock, StatusPill, Field, Modal, SettingsRow } from "../../components/ui";
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
import { PricingSettings } from "./pricing/PricingSettings";
import { capabilityOn } from "../../lib/features";
import { SpacePacksPanel } from "./SpacePacksPanel";
import { MakerspaceMembershipSettings } from "./MakerspaceMembershipSettings";
import { MakerspacePaymentSettings } from "./MakerspacePaymentSettings";
import { MakerspacePublicStatsSettings } from "./MakerspacePublicStatsSettings";
import { PublicStatsSettingsPanel } from "../stats/settings/PublicStatsSettingsPanel";
import { MakerspaceSubdomainSettings } from "./MakerspaceSubdomainSettings";
import { MakerspaceWebhookSettings } from "./MakerspaceWebhookSettings";
import { MakerspaceArchiveRequestPanel } from "./MakerspaceArchiveRequestPanel";
import { EventDefaultsSettings } from "./EventDefaultsSettings";
import { BorrowRequestAccessSettings } from "./BorrowRequestAccessSettings";
import { NotificationTimingSettings } from "./NotificationTimingSettings";
import { NotificationDestinations } from "./NotificationDestinations";
import { SpaceChatTemplates } from "./SpaceChatTemplates";
import { EvidenceRetentionPanel } from "./EvidenceRetentionPanel";
import { NotificationMuteMatrix } from "./NotificationMuteMatrix";
import { NotificationRecipientPicker } from "./NotificationRecipientPicker";
import { type Makerspace, useStaffGet } from "./StaffPanels";
import { MakerspaceLoanPolicySettings } from "./MakerspaceLoanPolicySettings";
import { LoanReservationPolicySettings } from "./LoanReservationPolicySettings";
import { SettingsHub } from "./SettingsHub";
import { staffTabPath } from "./staffTabs";
import { ChannelSetupPanel } from "../notifications/ChannelSetupPanel";
import { ChannelDeliveryLog } from "../notifications/ChannelDeliveryLog";
import { PresencePrivacySettings } from "../presence/PresencePrivacySettings";
import { PublicPageBuilder } from "../publicPages/PublicPageBuilder";
import { useHostingAvailability } from "../hosting/hostingApi";
import { HostingInvitations } from "./HostingInvitations";

type Props = {
  makerspace: Makerspace;
  isSuperadmin: boolean;
  canManageMakerspace: boolean;
  /** The actor's permitted tabs, so the hub links only to settings pages they can open. */
  allowedTabs?: readonly string[];
  singleTenantLocked?: boolean;
};

export function MakerspaceSettingsPanel({ makerspace, isSuperadmin, canManageMakerspace, allowedTabs = [], singleTenantLocked = false }: Props) {
  const [archiveOpen, setArchiveOpen] = useState(false);
  const queryClient = useQueryClient();
  const settings = useStaffGet<Makerspace>(
    ["makerspace-settings", makerspace.id],
    `/admin/makerspaces/${makerspace.id}`,
  );
  // Same cache entry as the archive panel: a pending request must be visible on the page,
  // not only after opening the request form.
  const archiveRequests = useQuery({ queryKey: ["staff", "archive-requests", makerspace.id] as const, enabled: canManageMakerspace,
    queryFn: () => staffRequest<MakerspaceArchiveRequest[]>(`/admin/makerspace/${makerspace.id}/archive-requests`) });
  const archivePending = Boolean(archiveRequests.data?.some(request => request.status === "pending"));
  const staffNotificationsEnabled =
    settings.data?.staff_notifications_enabled ?? makerspace.staff_notifications_enabled ?? true;
  const publicPrintStatusLookupPolicy =
    settings.data?.public_print_status_lookup_policy ?? makerspace.public_print_status_lookup_policy ?? "email_unverified";
  const enabledModules = settings.data?.enabled_modules ?? makerspace.enabled_modules ?? [];
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
      toast(t`Staff emails turned ${next ? "on" : "off"}.`, { undoKey: `settings-${makerspace.id}-updateStaffNotifications`, undo: async () => {
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



  const notificationsDisabled = settings.isLoading || updateStaffNotifications.isPending;
  const shared = { makerspace, settings: settings.data, loading: settings.isLoading };
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
        disabled={settings.isLoading || updatePrintStatusLookupPolicy.isPending}
        onChange={event => updatePrintStatusLookupPolicy.mutate(event.target.value as Makerspace["public_print_status_lookup_policy"])}>
        <option value="token_only">{t`Token only`}</option><option value="email_unverified">{t`Email lookup`}</option>
      </select></Field>
      {updatePrintStatusLookupPolicy.error ? <p role="alert" className="text-sm text-danger">{updatePrintStatusLookupPolicy.error.message}</p> : null}
    </div>
  </SettingsRow>;
  const sections: SettingsLayoutSection[] = [
    // This makerspace's local Space Manager or the platform superadmin (#115) edits the page.
    ...(canManageMakerspace ? [{ id: "public-page", title: t`Public page`, rows: <PublicPageBuilder owner={{ kind: "makerspace", id: makerspace.id }} /> }] : []),
    { id: "general", title: t`General`, rows: <>
      <MakerspaceGeneralSettings {...shared} />
      <MakerspaceLocationSettings {...shared} />
      {canManageMakerspace ? <MakerspaceProfileSettings makerspaceId={makerspace.id} /> : null}
    </> },
    { id: "branding", title: t`Branding & public site`, rows: <>
      <MakerspaceBrandingSettings {...shared} />{printRecovery}
      {settings.data?.platform_hosting === true ? <MakerspaceSubdomainSettings makerspace={makerspace} settings={settings.data} /> : null}
      <MakerspaceCustomDomainSettings {...shared} />
      {canManageMakerspace ? <MakerspaceDirectoryVisibility {...shared} /> : null}
    </> },
    // #170: Settings › Public stats; read-only for everyone but the Space Manager.
    { id: "public-stats", title: t`Public stats`, rows: <>
      <PublicStatsSettingsPanel key={makerspace.id} makerspaceId={makerspace.id} slug={makerspace.slug} />
      <MakerspacePublicStatsSettings {...shared} />
    </> },
    { id: "features", title: t`Features`, rows: <>
      <MakerspaceFeatureSettings {...shared} />
      {canManageMakerspace && (settings.data?.enabled_features ?? makerspace.enabled_features ?? []).includes("packs.import")
        ? <SpacePacksPanel key={makerspace.id} makerspaceId={makerspace.id} isSuperadmin={isSuperadmin} /> : null}
    </> },
    { id: "lending", title: t`Lending`, rows: <>
      {canManageMakerspace && (settings.data?.enabled_features ?? makerspace.enabled_features ?? []).includes("loans.enabled") ? <BorrowRequestAccessSettings makerspaceId={makerspace.id} /> : null}
      {enabledModules.includes("request_workflow") ? <MakerspaceLoanPolicySettings makerspaceId={makerspace.id} /> : null}
      {enabledModules.includes("request_workflow") && ["loans.pickup_windows", "loans.reservations", "loans.waitlist"].some(key => (settings.data?.enabled_features ?? makerspace.enabled_features ?? []).includes(key)) ? <LoanReservationPolicySettings makerspaceId={makerspace.id} /> : null}
      <MakerspaceReminderSettings {...shared} />
      {canManageMakerspace && (settings.data?.enabled_features ?? []).includes("inventory.kiosk") ? <KioskStationSettings makerspace={makerspace} /> : null}
    </> },
    // #183B: a section for a module that is off is not shown at all, not shown empty.
    ...(enabledModules.includes("membership") || enabledModules.includes("presence") ? [{ id: "membership", title: t`Membership`, rows: <>
      {enabledModules.includes("membership") ? <MakerspaceMembershipSettings {...shared} /> : null}<MakerspaceGeofenceSettings {...shared} />
    </> }] : []),
    ...(canManageMakerspace && enabledModules.includes("presence") ? [{ id: "presence", title: t`Presence privacy`,
      rows: <PresencePrivacySettings key={makerspace.id} makerspaceId={makerspace.id} slug={makerspace.slug} /> }] : []),
    ...(enabledModules.includes("bookings") ? [{ id: "bookings", title: t`Bookings`, rows: <>
      <MakerspaceBookingSettings {...shared} /><MakerspaceBookingRulesSettings makerspace={makerspace} />
    </> }] : []),
    ...(canManageMakerspace && enabledModules.includes("events") ? [{ id: "events", title: t`Events`,
      rows: <EventDefaultsSettings key={makerspace.id} makerspaceId={makerspace.id} /> }] : []),
    ...(enabledModules.includes("machines") || enabledModules.includes("printing")
      ? [{ id: "materials", title: t`Machines & materials`, rows: <MakerspaceFilamentSettings {...shared} /> }] : []),
    { id: "money", title: t`Money`, rows: <>
      <MakerspacePaymentSettings makerspace={settings.data ?? makerspace} />
      {canManageMakerspace ? <BillingDocumentsSettings key={makerspace.id} makerspaceId={makerspace.id} /> : null}
      {canManageMakerspace ? <TaxSettings key={`tax-${makerspace.id}`} makerspaceId={makerspace.id} /> : null}
      {canManageMakerspace && enabledModules.includes("events") ? <EventMoneySettings key={`event-money-${makerspace.id}`} makerspaceId={makerspace.id} /> : null}
    </> },
    ...(capabilityOn(settings.data ?? makerspace, "charges.pricing") ? [{ id: "pricing", title: t`Pricing`,
      description: t`Free or paid per area, the rates, member discounts and the currency new charges use.`,
      rows: <PricingSettings key={makerspace.id} makerspace={settings.data ?? makerspace} canManageMakerspace={canManageMakerspace} /> }] : []),
    { id: "notifications", title: t`Notifications`, rows: <>{staffEmail}
      {canManageMakerspace && enabledModules.includes("notifications") ? <NotificationTimingSettings key={makerspace.id} makerspaceId={makerspace.id} /> : null}
      <NotificationMuteMatrix makerspaceId={makerspace.id} /><NotificationRecipientPicker makerspaceId={makerspace.id} />
      <NotificationDestinations availableChannels={enabledModules} makerspaceId={makerspace.id} />
      {canManageMakerspace ? <SpaceChatTemplates makerspace={makerspace} /> : null}
    </> },
    ...(canManageMakerspace ? [{ id: "channels", title: t`Communication channels`,
      description: t`Choose the mediums this space uses and set up their credentials. Staff and members can only pick channels you turn on here.`,
      rows: <><ChannelSetupPanel key={makerspace.id} makerspaceId={makerspace.id} enabledModules={enabledModules} />
        <div className="py-4"><ChannelDeliveryLog key={makerspace.id} makerspaceId={makerspace.id} /></div></> }] : []),
    ...(canManageMakerspace && hostingAvailable ? [{ id: "hosting", title: t`Invite a makerspace`,
      rows: <div className="py-4"><HostingInvitations key={makerspace.id} scope={{ makerspaceId: makerspace.id }} /></div> }] : []),
    { id: "integrations", title: t`Email & integrations`, rows: <>
      <MakerspaceEmailSettings makerspace={makerspace} /><MakerspaceWebhookSettings makerspace={makerspace} />
      {isSuperadmin ? <ApiClientsTelegramSettings makerspace={makerspace} /> : null}
      <IntegrationHealthPanel makerspace={makerspace} isSuperadmin={isSuperadmin} />
    </> },
    ...(canManageMakerspace ? [{ id: "privacy", title: t`Privacy & evidence`,
      rows: <EvidenceRetentionPanel makerspaceId={makerspace.id} /> }] : []),
  ];
  // The hub goes first: search across every section here and the settings pages beside it.
  sections.unshift({ id: "start", title: t`Start here`, rows: <SettingsHub makerspace={settings.data ?? makerspace}
    sectionIds={sections.map(section => section.id)} allowedTabs={allowedTabs}
    tabHref={tab => consoleSessionHref(staffTabPath(tab, false, makerspace.slug, singleTenantLocked))} /> });
  return <>
    {/* Every editor owns its own query, so the parent GET never gates the page: while it
        loads the rows fall back to the `makerspace` prop (and disable via `loading`), and a
        failure is reported here instead of hiding payments, notifications and the rest. */}
    <SettingsLayout header={{ title: t`Makerspace settings`, subtitle: t`Make this space work for your community.`,
      meta: <>{settings.error ? <ErrorBlock className="w-full" onRetry={() => { void settings.refetch(); }}
        error={new Error(t`Couldn't load the latest settings (${settings.error.message}). Showing the last known values.`)} /> : null}</>,
      primary: { label: t`View public site`, href: `/m/${makerspace.slug}` } }}
      state={{ status: "ready" }}
      subnav="auto" sections={sections} danger={canManageMakerspace ? [{ title: t`Archive this makerspace`,
        consequence: archivePending ? "An archival request is pending superadmin review. Open it to see the request or withdraw it."
          : "Request archival for this makerspace. A superadmin must confirm before staff access is removed.",
        action: { label: archivePending ? t`View pending request` : t`Request archival`, onClick: () => setArchiveOpen(true) } }] : []} />
    <Modal open={archiveOpen} onClose={() => setArchiveOpen(false)} title={t`Archive this makerspace`} size="xl">
      <MakerspaceArchiveRequestPanel makerspaceId={makerspace.id} canManageMakerspace={canManageMakerspace} />
    </Modal>
  </>;
}
function statusLookupLabel(policy: Makerspace["public_print_status_lookup_policy"]) {
  return { token_only: "Token only", email_unverified: "Email lookup" }[policy ?? "email_unverified"];
}
