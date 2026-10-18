import { isProgrammePath } from "./features/events/programme/routeNames";
import { lazy, Suspense, type ReactNode } from "react";
import { Route, Routes, useLocation, useParams, useSearchParams } from "react-router-dom";
import { MakerspacePage } from "./features/public/MakerspacePage";
import { useTenantBootstrap } from "./features/inventory/usePublicInventory";
import { PublicDeskKioskPage } from "./features/kiosk/PublicDeskKioskPage";
import { ScannerPage } from "./features/kiosk/ScannerPage";
import { SuperadminPage } from "./features/staff/PlatformApps";
import { StaffApp } from "./features/staff/StaffApp";
import { CenteredCardLayout, PublicLayout } from "./components/layouts";
import { useTenant } from "./lib/tenant";
import { publicFamilies, publicHome } from "./lib/publicHome";
import { NotFoundPage } from "./features/NotFoundPage";
// Every public surface below is its own chunk. The makerspace page (which holds the catalogue) and the staff shell stay eager
// because they are the two pages almost every visit lands on; everything else loads when its
// route is first visited, so a lending-only install never downloads events, bookings or
// machines code. The staff panels inside StaffApp are already lazy (StaffTabContent.tsx).
const AboutPage = lazy(() => import("./features/AboutPage").then((m) => ({ default: m.AboutPage })));
const PublicBookingResourcePage = lazy(() => import("./features/bookings/PublicBookingResourcePage").then((m) => ({ default: m.PublicBookingResourcePage })));
const BookingDiscoverPage = lazy(() => import("./features/bookings/BookingDiscoverPage").then((m) => ({ default: m.BookingDiscoverPage })));
const PublicBookingsPage = lazy(() => import("./features/bookings/PublicBookingsPage").then((m) => ({ default: m.PublicBookingsPage })));
const PublicItemPage = lazy(() => import("./features/inventory/PublicItemPage").then((m) => ({ default: m.PublicItemPage })));
const PublicEventFeedbackPage = lazy(() => import("./features/inventory/PublicEventFeedbackPage").then((m) => ({ default: m.PublicEventFeedbackPage })));
const PublicEventDetailPage = lazy(() => import("./features/inventory/PublicEventDetailPage").then((m) => ({ default: m.PublicEventDetailPage })));
const MemberEventTicketPage = lazy(() => import("./features/events/MemberEventTicketPage").then((m) => ({ default: m.MemberEventTicketPage })));
const MemberEventHistoryPage = lazy(() => import("./features/events/MemberEventHistoryPage").then((m) => ({ default: m.MemberEventHistoryPage })));
const SpeakerClaimPage = lazy(() => import("./features/events/SpeakerClaimPage").then((m) => ({ default: m.SpeakerClaimPage })));
const EventDiscoverPage = lazy(() => import("./features/events/EventDiscoverPage").then((m) => ({ default: m.EventDiscoverPage })));
const PublicEventsPage = lazy(() => import("./features/inventory/PublicEventsPage").then((m) => ({ default: m.PublicEventsPage })));
const PublicMachinesPage = lazy(() => import("./features/inventory/PublicMachinesPage").then((m) => ({ default: m.PublicMachinesPage })));
const PublicSelfCheckoutPage = lazy(() => import("./features/inventory/PublicSelfCheckoutPage").then((m) => ({ default: m.PublicSelfCheckoutPage })));
const ArchivedPayments = lazy(() => import("./features/members/ArchivedPayments").then((m) => ({ default: m.ArchivedPayments })));
const MemberArea = lazy(() => import("./features/members/MemberArea").then((m) => ({ default: m.MemberArea })));
const MemberAccountPage = lazy(() => import("./features/members/MemberAccountPage").then((m) => ({ default: m.MemberAccountPage })));
const PublicPrintRequestPage = lazy(() => import("./features/printing/PublicPrintRequestPage").then((m) => ({ default: m.PublicPrintRequestPage })));
const PublicOrganizationPage = lazy(() => import("./features/organizations/PublicOrganizationPage").then((m) => ({ default: m.PublicOrganizationPage })));
const OrganizationInvitationRedeemPage = lazy(() => import("./features/organizations/OrganizationInvitationRedeemPage").then((m) => ({ default: m.OrganizationInvitationRedeemPage })));
const ResetPasswordPage = lazy(() => import("./features/staff/ResetPasswordPage").then((m) => ({ default: m.ResetPasswordPage })));
const ConsolePasswordResetPage = lazy(() => import("./features/auth/ConsolePasswordResetPage").then((m) => ({ default: m.ConsolePasswordResetPage })));
const EventCheckInStationPage = lazy(() => import("./features/events/EventCheckInStationPage").then((m) => ({ default: m.EventCheckInStationPage })));
const KioskStationPage = lazy(() => import("./features/kiosk/KioskStationPage").then((m) => ({ default: m.KioskStationPage })));
const PublicStatsPage = lazy(() => import("./features/stats/PublicStatsPage").then((m) => ({ default: m.PublicStatsPage })));
const PublicProfilePage = lazy(() => import("./features/profile/PublicProfilePage").then((m) => ({ default: m.PublicProfilePage })));
const PresenceNowPage = lazy(() => import("./features/presence/PresenceNowPage").then((m) => ({ default: m.PresenceNowPage })));
const PublicWebsiteDetailPage = lazy(() => import("./features/events/PublicWebsiteDetailPage").then((m) => ({ default: m.PublicWebsiteDetailPage })));

// Tenant capabilities choose the home independently of the deployment edition.

function FamilyHome() {
  const tenant = useTenant();
  const { slug = "" } = useParams();
  const bootstrapQuery = useTenantBootstrap(slug, tenant.mode === "central" && Boolean(slug));
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const homeHref = tenant.mode === "single" ? "/" : `/m/${slug}`;
  const memberHref = tenant.mode === "single" ? "/member" : `/m/${slug}/member`;
  const [params] = useSearchParams();
  if (!bootstrap) {
    if (bootstrapQuery.error) return <PublicLayout state={{ status: "error", error: "Couldn't load this space. Try again.", onRetry: () => void bootstrapQuery.refetch() }}
      makerspace={{ name: "Space Works", slug, homeHref }} headerAction={{ label: "Sign in", href: memberHref }} nav={[]} header={{ title: "We couldn't load this space" }}
      footer={{ credit: "Powered by Space Works", links: [] }}><span /></PublicLayout>;
    return <RouteFallback />;
  }
  // Old home links that opened a space (?space=, ?confirmation=) still land on the bookings page.
  if ((params.has("space") || params.has("confirmation")) && publicFamilies(bootstrap).includes("bookings")) return <PublicBookingsPage />;
  switch (publicHome(bootstrap)) {
    case "makerspace": return <MakerspacePage />;
    case "events": return <PublicEventsPage />;
    case "bookings": return <PublicBookingsPage />;
    case "machines": return <PublicMachinesPage />;
    case "membership": return <MemberArea />;
    default: return <PublicLayout state={{ status: "ready" }} isEmpty empty={{ message: `${bootstrap.branding.display_name || bootstrap.makerspace.name} hasn't published anything yet. Check back soon.` }}
      makerspace={{ name: bootstrap.branding.display_name || bootstrap.makerspace.name, slug, homeHref }} headerAction={{ label: "Sign in", href: memberHref }} nav={[]}
      header={{ title: bootstrap.branding.display_name || bootstrap.makerspace.name }} footer={{ credit: "Powered by Space Works", links: [] }}><span /></PublicLayout>;
  }
}
const MfaAccountPage = lazy(() => import("./features/auth/MfaAccountPage").then((m) => ({ default: m.MfaAccountPage })));
const StaffInvitationAcceptPage = lazy(() => import("./features/auth/StaffInvitationAcceptPage").then((m) => ({ default: m.StaffInvitationAcceptPage })));
const BookingStaffInvitePage = lazy(() => import("./features/staff/BookingStaffInvitePage").then((m) => ({ default: m.BookingStaffInvitePage })));
const EventStaffInvitePage = lazy(() => import("./features/staff/EventStaffInvitePage").then((m) => ({ default: m.EventStaffInvitePage })));

function RouteFallback() {
  return <div role="status"><CenteredCardLayout state={{ status: "loading" }} title="Opening Space Works…" body=""
    primary={{ label: "Loading…", disabled: true, disabledReason: "The page is opening." }} /></div>;
}

// Canonical links also use the tenant prefix on token-configured frontends.
function SingleTenantEvent() {
  const tenant = useTenant();
  const { slug } = useParams();
  if (tenant.loading) return <RouteFallback />;
  return slug === tenant.slug ? <PublicEventDetailPage /> : <NotFoundPage />;
}

const ProgrammeRoutes = lazy(() => import("./features/events/programme/ProgrammeRoutes").then(m => ({ default: m.ProgrammeRoutes })));

export function AppRoutes({ mode, landing }: { mode: "single" | "central"; landing: ReactNode }) {
  const location = useLocation();
  let routes: ReactNode;
  if (isProgrammePath(location.pathname)) {
    routes = <ProgrammeRoutes />;
  } else if (/^\/(?:m\/[^/]+\/)?admin\/reset-password\/?$/.test(location.pathname)) {
    routes = <Routes>
      <Route path="/admin/reset-password" element={<ConsolePasswordResetPage />} />
      <Route path="/m/:slug/admin/reset-password" element={<ConsolePasswordResetPage />} />
    </Routes>;
  } else if (location.pathname === "/mfa") {
    routes = <Routes><Route path="/mfa" element={<MfaAccountPage />} /></Routes>;
  } else if (location.pathname === "/staff-invitations/accept") {
    routes = <Routes><Route path="/staff-invitations/accept" element={<StaffInvitationAcceptPage />} /></Routes>;
  } else if (location.pathname === "/staff/booking-invite") {
    routes = <Routes><Route path="/staff/booking-invite" element={<BookingStaffInvitePage />} /></Routes>;
  } else if (location.pathname === "/staff/event-invite") {
    routes = <Routes><Route path="/staff/event-invite" element={<EventStaffInvitePage />} /></Routes>;
  } else if (location.pathname === "/member/archived") {
    routes = <Routes><Route path="/member/archived" element={<ArchivedPayments />} /></Routes>;
  } else if (location.pathname.startsWith("/organization-invitations/redeem/")) {
    routes = <Routes><Route path="/organization-invitations/redeem/:token" element={<OrganizationInvitationRedeemPage />} /></Routes>;
  } else if (location.pathname === "/discover/bookings") {
    routes = <Routes><Route path="/discover/bookings" element={<BookingDiscoverPage />} /></Routes>;
  } else if (location.pathname === "/discover") {
    routes = <Routes><Route path="/discover" element={<EventDiscoverPage />} /></Routes>;
  } else if (mode === "single") {
    routes = <Routes>
      <Route path="/" element={<FamilyHome />} />
      <Route path="/items/:itemId" element={<PublicItemPage />} />
      <Route path="/checkout" element={<PublicSelfCheckoutPage />} />
      <Route path="/events" element={<PublicEventsPage />} />
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
      <Route path="/member" element={<MemberArea />} />
      <Route path="/member/account" element={<MemberAccountPage />} />
      <Route path="/member/events/:registrationId/ticket" element={<MemberEventTicketPage />} />
      <Route path="/member/events/history" element={<MemberEventHistoryPage />} />
      <Route path="/member/speaker-claim" element={<SpeakerClaimPage />} />
      <Route path="/member/:memberTab" element={<MemberArea />} />
      <Route path="/stats" element={<PublicStatsPage />} />
      <Route path="/now" element={<PresenceNowPage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/admin/*" element={<StaffApp />} />
      <Route path="/guest-admin/*" element={<StaffApp guestOnly />} />
      <Route path="/scanner" element={<ScannerPage />} />
      <Route path="/kiosk/:stationToken" element={<KioskStationPage />} />
      {/* Public profiles: after every explicit route, before the catch-all. */}
      <Route path="/:handle" element={<PublicProfilePage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>;
  } else {
    routes = <Routes>
      <Route path="/" element={landing} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/o/:organizationSlug" element={<PublicOrganizationPage />} />
      <Route path="/m/:slug" element={<FamilyHome />} />
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
      <Route path="/m/:slug/member" element={<MemberArea />} />
      <Route path="/m/:slug/member/account" element={<MemberAccountPage />} />
      <Route path="/m/:slug/member/events/:registrationId/ticket" element={<MemberEventTicketPage />} />
      <Route path="/m/:slug/member/events/history" element={<MemberEventHistoryPage />} />
      <Route path="/m/:slug/member/speaker-claim" element={<SpeakerClaimPage />} />
      <Route path="/member" element={<MemberArea />} />
      <Route path="/member/account" element={<MemberAccountPage />} />
      <Route path="/member/events/:registrationId/ticket" element={<MemberEventTicketPage />} />
      <Route path="/m/:slug/member/:memberTab" element={<MemberArea />} />
      <Route path="/member/:memberTab" element={<MemberArea />} />
      <Route path="/m/:slug/stats" element={<PublicStatsPage />} />
      <Route path="/m/:slug/now" element={<PresenceNowPage />} />
      <Route path="/m/:slug/kiosk/:stationToken" element={<KioskStationPage />} />
      <Route path="/m/:slug/scanner" element={<ScannerPage />} />
      <Route path="/kiosk/:slug" element={<PublicDeskKioskPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/admin/*" element={<StaffApp />} />
      <Route path="/guest-admin/*" element={<StaffApp guestOnly />} />
      <Route path="/scanner" element={<ScannerPage />} />
      <Route path="/superadmin" element={<SuperadminPage />} />
      {/* Public profiles: after every explicit route, before the catch-all. */}
      <Route path="/:handle" element={<PublicProfilePage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>;
  }
  return <Suspense fallback={<RouteFallback />}>{routes}</Suspense>;
}
