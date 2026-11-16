import { isProgrammePath } from "./features/events/programme/routeNames";
import { isEventAddonPath } from "./features/events/eventAddons/routeNames";
import { isCardPath } from "./features/cards/routeNames";
import { isDonationPath } from "./features/donations/routeNames";
import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation, useParams, useSearchParams } from "react-router-dom";
import { AboutLandingGate } from "./features/hub/LandingGate";
import { SingleTenantHome } from "./features/public/SingleTenantHome";
import { FamilyHome, RouteFallback } from "./features/public/FamilyHome";
import { PublicDeskKioskPage } from "./features/kiosk/PublicDeskKioskPage";
import { ScannerPage } from "./features/kiosk/ScannerPage";
import { useTenant } from "./lib/tenant";
import { NotFoundPage } from "./features/NotFoundPage";
import { PausedTenantGate, publicTenantSlug } from "./features/platformNotices/PausedTenantGate";
import {
  PublicOrganizationPage, OrganizationInvitationRedeemPage, ResetPasswordPage, ConsolePasswordResetPage,
  AccountRestorePage, EventCheckInStationPage, KioskStationPage, PublicStatsPage, PublicStatsTvPage,
  PublicHandlePage, PublicEventCodePage, PayLinkPage, PresenceNowPage, SpaceDisplayPage, PublicWebsiteDetailPage, HostingRequestPage,
  HostingInvitePage, HostingRequestStatusPage, PublicShopPage, PublicShopProductPage, ShopOrderStatusPage,
  MemberShopOrdersPage, MfaAccountPage, NotMePage, StaffInvitationAcceptPage, BookingStaffInvitePage, EventStaffInvitePage,
  ProgrammeRoutes, CardRoutes, MemberEventAddonRoutes, DonationRoutes, HelpPage, DocsPage,
  TechnicianOptInPage, MyMachineJobsPage, AttendanceReplyPage, CrewSignupPage, ApplicationReviewsPage,
  MachineJobPage, UseMachinePage, MySessionsPage, SupervisedSessionsPage, OAuthConsentPage, PersonalApiAccessPage,
  SpeakerClaimPage, EventDiscoverPage, PublicSelfCheckoutPage, ArchivedPayments, MemberAccountPage, PublicPrintRequestPage, PublicMachineServiceStatusPage, JobRequestPage, UnsubscribePage, LegalPage,
  MemberProfilePage, ProfileByAccountPage, StaffApp, SuperadminPage,
} from "./AppRoutesLazyPages";
// Every public surface below is its own chunk. The makerspace overview stays eager
// because almost every visit lands on it; everything else loads when its
// route is first visited, so a lending-only install never downloads events, bookings or
// machines code. StaffApp and SuperadminPage are lazy too (keeps the entry chunk under 500 kB); the staff
// panels inside are lazy again (StaffTabContent.tsx).
const MemberBorrowingHistoryPage = lazy(() => import("./features/members/MemberBorrowingHistoryPage").then(m => ({ default: m.MemberBorrowingHistoryPage })));
const PublicInventoryRoute = lazy(() => import("./features/inventory/PublicInventoryRoute").then(m => ({ default: m.PublicInventoryRoute })));
const HubLandingPage = lazy(() => import("./features/hub/HubLandingPage").then(m => ({ default: m.HubLandingPage })));
const FeaturesPage = lazy(() => import("./features/hub/FeaturesPage").then((m) => ({ default: m.FeaturesPage })));
const FeatureModulePage = lazy(() => import("./features/hub/featuresPage/FeatureModulePage").then((m) => ({ default: m.FeatureModulePage })));
const SpacesPage = lazy(() => import("./features/discover/spaces/SpacesPage").then((m) => ({ default: m.SpacesPage })));
const PublicOrganizationDirectory = lazy(() => import("./features/organizations/PublicOrganizationDirectory").then((m) => ({ default: m.PublicOrganizationDirectory })));
const PublicBookingResourcePage = lazy(() => import("./features/bookings/PublicBookingResourcePage").then((m) => ({ default: m.PublicBookingResourcePage })));
const BookingDiscoverPage = lazy(() => import("./features/bookings/BookingDiscoverPage").then((m) => ({ default: m.BookingDiscoverPage })));
const PublicBookingsPage = lazy(() => import("./features/bookings/PublicBookingsPage").then((m) => ({ default: m.PublicBookingsPage })));
const PublicItemPage = lazy(() => import("./features/inventory/PublicItemPage").then((m) => ({ default: m.PublicItemPage })));
const PublicEventFeedbackPage = lazy(() => import("./features/inventory/PublicEventFeedbackPage").then((m) => ({ default: m.PublicEventFeedbackPage })));
const PublicEventDetailPage = lazy(() => import("./features/inventory/PublicEventDetailPage").then((m) => ({ default: m.PublicEventDetailPage })));
const TicketClaimPage = lazy(() => import("./features/events/ticketing/TicketClaimPage").then((m) => ({ default: m.TicketClaimPage })));
const MemberOrdersPage = lazy(() => import("./features/events/ticketing/MemberOrdersPage").then((m) => ({ default: m.MemberOrdersPage })));
const MemberSeriesPassPage = lazy(() => import("./features/events/ticketing/MemberSeriesPassPage").then((m) => ({ default: m.MemberSeriesPassPage })));
const MemberEventTicketPage = lazy(() => import("./features/events/MemberEventTicketPage").then((m) => ({ default: m.MemberEventTicketPage })));
const MemberEventHistoryPage = lazy(() => import("./features/events/MemberEventHistoryPage").then((m) => ({ default: m.MemberEventHistoryPage })));
const PublicEventsPage = lazy(() => import("./features/inventory/PublicEventsPage").then((m) => ({ default: m.PublicEventsPage })));
const PublicMachinesPage = lazy(() => import("./features/inventory/PublicMachinesPage").then((m) => ({ default: m.PublicMachinesPage })));
const MemberArea = lazy(() => import("./features/members/MemberArea").then((m) => ({ default: m.MemberArea })));

// Canonical links also use the tenant prefix on token-configured frontends.
function SingleTenantEvent() {
  const tenant = useTenant();
  const { slug } = useParams();
  if (tenant.loading) return <RouteFallback />;
  return slug === tenant.slug ? <PublicEventDetailPage /> : <NotFoundPage />;
}

function MemberTabRoute() {
  const { slug, memberTab } = useParams();
  const [search] = useSearchParams();
  // Retain registered inbox OAuth redirects for account-only owners, even when
  // membership or the optional inbox is absent. Verification still binds server state.
  if (memberTab === "inbox" && search.has("state")) return <Navigate replace
    to={`${slug ? `/m/${slug}` : ""}/member/account-portal?${search}`} />;
  return <MemberArea />;
}

export function AppRoutes({ mode, landing }: { mode: "single" | "central"; landing: ReactNode }) {
  const location = useLocation();
  let routes: ReactNode;
  if (isProgrammePath(location.pathname)) {
    routes = <ProgrammeRoutes />;
  } else if (isEventAddonPath(location.pathname)) {
    routes = <MemberEventAddonRoutes />;
  } else if (isCardPath(location.pathname)) {
    routes = <CardRoutes />;
  } else if (isDonationPath(location.pathname)) {
    routes = <DonationRoutes />;
  } else if (/^\/(?:m\/[^/]+\/)?admin\/reset-password\/?$/.test(location.pathname)) {
    routes = <Routes>
      <Route path="/admin/reset-password" element={<ConsolePasswordResetPage />} />
      <Route path="/m/:slug/admin/reset-password" element={<ConsolePasswordResetPage />} />
    </Routes>;
  } else if (location.pathname === "/account/restore") {
    routes = <Routes><Route path="/account/restore" element={<AccountRestorePage />} /></Routes>;
  } else if (location.pathname === "/oauth/authorize") {
    routes = <Routes><Route path="/oauth/authorize" element={<OAuthConsentPage />} /></Routes>;
  } else if (location.pathname === "/account/api-access") {
    routes = <Routes><Route path="/account/api-access" element={<PersonalApiAccessPage />} /></Routes>;
  } else if (location.pathname === "/mfa") {
    routes = <Routes><Route path="/mfa" element={<MfaAccountPage />} /></Routes>;
  } else if (location.pathname === "/security/not-me") {
    routes = <Routes><Route path="/security/not-me" element={<NotMePage />} /></Routes>;
  } else if (location.pathname === "/staff-invitations/accept") {
    routes = <Routes><Route path="/staff-invitations/accept" element={<StaffInvitationAcceptPage />} /></Routes>;
  } else if (location.pathname === "/staff/booking-invite") {
    routes = <Routes><Route path="/staff/booking-invite" element={<BookingStaffInvitePage />} /></Routes>;
  } else if (location.pathname === "/staff/event-invite") {
    routes = <Routes><Route path="/staff/event-invite" element={<EventStaffInvitePage />} /></Routes>;
  } else if (location.pathname === "/member/archived") {
    routes = <Routes><Route path="/member/archived" element={<ArchivedPayments />} /></Routes>;
  } else if (location.pathname.startsWith("/unsubscribe/")) {
    routes = <Routes><Route path="/unsubscribe/:token" element={<UnsubscribePage />} /></Routes>;
  } else if (location.pathname.startsWith("/pay/")) {
    routes = <Routes><Route path="/pay/:token" element={<PayLinkPage />} /></Routes>;
  } else if (location.pathname.startsWith("/organization-invitations/redeem/")) {
    routes = <Routes><Route path="/organization-invitations/redeem/:token" element={<OrganizationInvitationRedeemPage />} /></Routes>;
  } else if (location.pathname === "/display") {
    // Decision 307: the paired TV screen. Before every tenant route: it has no tenant until staff claim it.
    routes = <Routes><Route path="/display" element={<SpaceDisplayPage />} /></Routes>;
  } else if (location.pathname === "/discover/bookings") {
    routes = <Routes><Route path="/discover/bookings" element={<BookingDiscoverPage />} /></Routes>;
  } else if (location.pathname === "/discover") {
    routes = <Routes><Route path="/discover" element={<EventDiscoverPage />} /></Routes>;
  } else if (location.pathname === "/privacy" || location.pathname === "/terms") {
    routes = <Routes><Route path="/privacy" element={<LegalPage slug="privacy" />} /><Route path="/terms" element={<LegalPage slug="terms" />} /></Routes>;
  } else if (mode === "single") {
    routes = <Routes>
      <Route path="/" element={<FamilyHome />} />
      <Route path="/m/:slug" element={<SingleTenantHome />} />
      <Route path="/spaces" element={<SpacesPage />} />
      <Route path="/inventory" element={<PublicInventoryRoute />} />
      <Route path="/items/:itemId" element={<PublicItemPage />} />
      <Route path="/checkout" element={<PublicSelfCheckoutPage />} />
      <Route path="/events" element={<PublicEventsPage />} />
      <Route path="/e/:publicToken" element={<PublicEventCodePage />} />
      <Route path="/o/:organizationSlug" element={<PublicOrganizationPage />} />
      <Route path="/events/:publicToken" element={<PublicEventDetailPage />} />
      <Route path="/events/:publicToken/schedule" element={<PublicWebsiteDetailPage view="schedule" />} />
      <Route path="/events/:publicToken/sessions/:sessionSlug" element={<PublicWebsiteDetailPage view="session" />} />
      <Route path="/events/:publicToken/speakers/:speakerSlug" element={<PublicWebsiteDetailPage view="speaker" />} />
      <Route path="/m/:slug/events/:publicToken/schedule" element={<PublicWebsiteDetailPage view="schedule" />} />
      <Route path="/m/:slug/events/:publicToken/sessions/:sessionSlug" element={<PublicWebsiteDetailPage view="session" />} />
      <Route path="/m/:slug/events/:publicToken/speakers/:speakerSlug" element={<PublicWebsiteDetailPage view="speaker" />} />
      <Route path="/m/:slug/events/:publicToken" element={<SingleTenantEvent />} />
      <Route path="/events/:publicToken/feedback" element={<PublicEventFeedbackPage />} />
      <Route path="/event-check-in/:stationToken" element={<EventCheckInStationPage />} />
      <Route path="/machines" element={<PublicMachinesPage />} />
      <Route path="/bookings" element={<PublicBookingsPage />} />
      <Route path="/bookings/:resourceToken" element={<PublicBookingResourcePage />} />
      <Route path="/m/:slug/bookings/:resourceToken" element={<PublicBookingResourcePage />} />
      <Route path="/print" element={<PublicPrintRequestPage />} />
      <Route path="/machine-service/requests/:publicToken" element={<PublicMachineServiceStatusPage />} />
      <Route path="/machine-jobs/new" element={<JobRequestPage />} />
      <Route path="/technician-opt-in/:token" element={<TechnicianOptInPage />} />
      <Route path="/member/machine-jobs" element={<MyMachineJobsPage />} />
      <Route path="/member/machine-jobs/:jobId" element={<MachineJobPage />} />
      <Route path="/machines/:machineId/use" element={<UseMachinePage />} />
      <Route path="/member/machine-sessions" element={<MySessionsPage />} />
      <Route path="/machines/:machineId/supervise" element={<SupervisedSessionsPage />} />
      <Route path="/member/supervised-sessions" element={<SupervisedSessionsPage />} />
      <Route path="/member" element={<MemberArea />} />
      <Route path="/member/loans/history" element={<MemberBorrowingHistoryPage />} />
      <Route path="/member/account" element={<MemberAccountPage />} />
      <Route path="/member/profile" element={<MemberProfilePage />} />
      <Route path="/profiles/by-account/:accountId" element={<ProfileByAccountPage />} />
      <Route path="/member/events/:registrationId/ticket" element={<MemberEventTicketPage />} />
      <Route path="/member/events/history" element={<MemberEventHistoryPage />} />
      <Route path="/member/events/:eventId/attendance" element={<AttendanceReplyPage />} />
      <Route path="/member/events/:eventId/crew" element={<CrewSignupPage />} />
      <Route path="/member/application-reviews" element={<ApplicationReviewsPage />} />
      <Route path="/member/speaker-claim" element={<SpeakerClaimPage />} />
      <Route path="/member/orders" element={<MemberOrdersPage />} />
      <Route path="/member/orders/:orderId" element={<MemberOrdersPage />} />
      <Route path="/member/series/:seriesId/passes" element={<MemberSeriesPassPage />} />
      <Route path="/member/ticket-claims/:token" element={<TicketClaimPage kind="claim" />} />
      <Route path="/member/ticket-transfers/:token" element={<TicketClaimPage kind="transfer" />} />
      <Route path="/member/:memberTab" element={<MemberTabRoute />} />
      <Route path="/shop" element={<PublicShopPage />} />
      <Route path="/shop/order/:token" element={<ShopOrderStatusPage />} />
      <Route path="/shop/:productSlug" element={<PublicShopProductPage />} />
      <Route path="/m/:slug/shop" element={<PublicShopPage />} />
      <Route path="/m/:slug/shop/order/:token" element={<ShopOrderStatusPage />} />
      <Route path="/m/:slug/shop/:productSlug" element={<PublicShopProductPage />} />
      <Route path="/member/shop-orders" element={<MemberShopOrdersPage />} />
      <Route path="/member/shop-orders/:orderId" element={<MemberShopOrdersPage />} />
      <Route path="/stats" element={<PublicStatsPage />} />
      <Route path="/stats/tv" element={<PublicStatsTvPage />} />
      <Route path="/now" element={<PresenceNowPage />} />
      <Route path="/about" element={<AboutLandingGate landing={<HubLandingPage />} />} />
      <Route path="/features" element={<FeaturesPage />} />
      <Route path="/features/:module" element={<FeatureModulePage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/admin/*" element={<StaffApp />} />
      <Route path="/guest-admin/*" element={<StaffApp guestOnly />} />
      <Route path="/scanner" element={<ScannerPage />} />
      <Route path="/kiosk/:stationToken" element={<KioskStationPage />} />
      <Route path="/help" element={<HelpPage />} />
      <Route path="/help/:sectionId" element={<HelpPage />} />
      <Route path="/help/:sectionId/:articleSlug" element={<HelpPage />} />
      <Route path="/docs/*" element={<DocsPage />} />
      {/* Public profiles: after every explicit route, before the catch-all. */}
      <Route path="/:handle" element={<PublicHandlePage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>;
  } else {
    routes = <Routes>
      <Route path="/" element={landing} />
      <Route path="/about" element={<AboutLandingGate landing={<HubLandingPage />} />} />
      <Route path="/features" element={<FeaturesPage />} />
      <Route path="/features/:module" element={<FeatureModulePage />} />
      <Route path="/spaces" element={<SpacesPage />} />
      <Route path="/organizations" element={<PublicOrganizationDirectory />} />
      <Route path="/o/:organizationSlug" element={<PublicOrganizationPage />} />
      <Route path="/e/:publicToken" element={<PublicEventCodePage />} />
      <Route path="/m/:slug" element={<FamilyHome />} />
      <Route path="/m/:slug/inventory" element={<PublicInventoryRoute />} />
      <Route path="/m/:slug/items/:itemId" element={<PublicItemPage />} />
      <Route path="/m/:slug/checkout" element={<PublicSelfCheckoutPage />} />
      <Route path="/m/:slug/events" element={<PublicEventsPage />} />
      <Route path="/m/:slug/events/:publicToken" element={<PublicEventDetailPage />} />
      <Route path="/m/:slug/events/:publicToken/schedule" element={<PublicWebsiteDetailPage view="schedule" />} />
      <Route path="/m/:slug/events/:publicToken/sessions/:sessionSlug" element={<PublicWebsiteDetailPage view="session" />} />
      <Route path="/m/:slug/events/:publicToken/speakers/:speakerSlug" element={<PublicWebsiteDetailPage view="speaker" />} />
      <Route path="/m/:slug/events/:publicToken/feedback" element={<PublicEventFeedbackPage />} />
      <Route path="/m/:slug/event-check-in/:stationToken" element={<EventCheckInStationPage />} />
      <Route path="/m/:slug/machines" element={<PublicMachinesPage />} />
      <Route path="/m/:slug/bookings" element={<PublicBookingsPage />} />
      <Route path="/m/:slug/bookings/:resourceToken" element={<PublicBookingResourcePage />} />
      <Route path="/m/:slug/admin/*" element={<StaffApp />} />
      <Route path="/m/:slug/print" element={<PublicPrintRequestPage />} />
      <Route path="/m/:slug/machine-service/requests/:publicToken" element={<PublicMachineServiceStatusPage />} />
      <Route path="/m/:slug/machine-jobs/new" element={<JobRequestPage />} />
      <Route path="/m/:slug/technician-opt-in/:token" element={<TechnicianOptInPage />} />
      <Route path="/m/:slug/member/machine-jobs" element={<MyMachineJobsPage />} />
      <Route path="/m/:slug/member/machine-jobs/:jobId" element={<MachineJobPage />} />
      <Route path="/m/:slug/machines/:machineId/use" element={<UseMachinePage />} />
      <Route path="/m/:slug/member/machine-sessions" element={<MySessionsPage />} />
      <Route path="/m/:slug/machines/:machineId/supervise" element={<SupervisedSessionsPage />} />
      <Route path="/m/:slug/member/supervised-sessions" element={<SupervisedSessionsPage />} />
      <Route path="/m/:slug/member" element={<MemberArea />} />
      <Route path="/m/:slug/member/loans/history" element={<MemberBorrowingHistoryPage />} />
      <Route path="/m/:slug/member/account" element={<MemberAccountPage />} />
      <Route path="/m/:slug/member/events/:registrationId/ticket" element={<MemberEventTicketPage />} />
      <Route path="/m/:slug/member/events/history" element={<MemberEventHistoryPage />} />
      <Route path="/m/:slug/member/events/:eventId/attendance" element={<AttendanceReplyPage />} />
      <Route path="/m/:slug/member/events/:eventId/crew" element={<CrewSignupPage />} />
      <Route path="/m/:slug/member/application-reviews" element={<ApplicationReviewsPage />} />
      <Route path="/m/:slug/member/speaker-claim" element={<SpeakerClaimPage />} />
      <Route path="/member" element={<MemberArea />} />
      <Route path="/member/account" element={<MemberAccountPage />} />
      <Route path="/member/profile" element={<MemberProfilePage />} />
      <Route path="/profiles/by-account/:accountId" element={<ProfileByAccountPage />} />
      <Route path="/member/events/:registrationId/ticket" element={<MemberEventTicketPage />} />
      <Route path="/m/:slug/member/orders" element={<MemberOrdersPage />} />
      <Route path="/m/:slug/member/orders/:orderId" element={<MemberOrdersPage />} />
      <Route path="/m/:slug/member/series/:seriesId/passes" element={<MemberSeriesPassPage />} />
      <Route path="/m/:slug/member/ticket-claims/:token" element={<TicketClaimPage kind="claim" />} />
      <Route path="/m/:slug/member/ticket-transfers/:token" element={<TicketClaimPage kind="transfer" />} />
      <Route path="/member/orders" element={<MemberOrdersPage />} />
      <Route path="/member/orders/:orderId" element={<MemberOrdersPage />} />
      <Route path="/member/series/:seriesId/passes" element={<MemberSeriesPassPage />} />
      <Route path="/member/ticket-claims/:token" element={<TicketClaimPage kind="claim" />} />
      <Route path="/member/ticket-transfers/:token" element={<TicketClaimPage kind="transfer" />} />
      <Route path="/m/:slug/member/:memberTab" element={<MemberTabRoute />} />
      <Route path="/member/:memberTab" element={<MemberTabRoute />} />
      <Route path="/m/:slug/shop" element={<PublicShopPage />} />
      <Route path="/m/:slug/shop/order/:token" element={<ShopOrderStatusPage />} />
      <Route path="/m/:slug/shop/:productSlug" element={<PublicShopProductPage />} />
      <Route path="/m/:slug/member/shop-orders" element={<MemberShopOrdersPage />} />
      <Route path="/m/:slug/member/shop-orders/:orderId" element={<MemberShopOrdersPage />} />
      <Route path="/member/shop-orders" element={<MemberShopOrdersPage />} />
      <Route path="/member/shop-orders/:orderId" element={<MemberShopOrdersPage />} />
      <Route path="/m/:slug/stats" element={<PublicStatsPage />} />
      <Route path="/m/:slug/stats/tv" element={<PublicStatsTvPage />} />
      <Route path="/m/:slug/now" element={<PresenceNowPage />} />
      <Route path="/m/:slug/kiosk/:stationToken" element={<KioskStationPage />} />
      <Route path="/m/:slug/scanner" element={<ScannerPage />} />
      <Route path="/kiosk/:slug" element={<PublicDeskKioskPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/admin/*" element={<StaffApp />} />
      <Route path="/guest-admin/*" element={<StaffApp guestOnly />} />
      <Route path="/scanner" element={<ScannerPage />} />
      <Route path="/superadmin" element={<SuperadminPage />} />
      {/* Managed hosting requests exist only on the central origin. */}
      <Route path="/hosting" element={<HostingRequestPage />} />
      <Route path="/hosting/invite" element={<HostingInvitePage />} />
      <Route path="/hosting/request" element={<HostingRequestStatusPage />} />
      <Route path="/help" element={<HelpPage />} />
      <Route path="/help/:sectionId" element={<HelpPage />} />
      <Route path="/help/:sectionId/:articleSlug" element={<HelpPage />} />
      <Route path="/m/:slug/help" element={<HelpPage />} />
      <Route path="/m/:slug/help/:sectionId" element={<HelpPage />} />
      <Route path="/m/:slug/help/:sectionId/:articleSlug" element={<HelpPage />} />
      <Route path="/m/:slug/privacy" element={<LegalPage slug="privacy" />} />
      <Route path="/m/:slug/terms" element={<LegalPage slug="terms" />} />
      <Route path="/docs/*" element={<DocsPage />} />
      {/* Public profiles: after every explicit route, before the catch-all. */}
      <Route path="/:handle" element={<PublicHandlePage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>;
  }
  const publicSlug = mode === "central" ? publicTenantSlug(location.pathname) : "";
  return <Suspense fallback={<RouteFallback />}>{publicSlug ? <PausedTenantGate slug={publicSlug}>{routes}</PausedTenantGate> : routes}</Suspense>;
}
