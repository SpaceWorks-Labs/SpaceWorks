/** Lazy public and member pages for `AppRoutes` (split out at the 300-line ceiling; each is its own chunk). */
import { lazy } from "react";

export const PublicOrganizationPage = lazy(() => import("./features/organizations/PublicOrganizationPage").then((m) => ({ default: m.PublicOrganizationPage })));
export const OrganizationInvitationRedeemPage = lazy(() => import("./features/organizations/OrganizationInvitationRedeemPage").then((m) => ({ default: m.OrganizationInvitationRedeemPage })));
export const ResetPasswordPage = lazy(() => import("./features/staff/ResetPasswordPage").then((m) => ({ default: m.ResetPasswordPage })));
export const ConsolePasswordResetPage = lazy(() => import("./features/auth/ConsolePasswordResetPage").then((m) => ({ default: m.ConsolePasswordResetPage })));
export const AccountRestorePage = lazy(() => import("./features/auth/AccountRestorePage").then((m) => ({ default: m.AccountRestorePage })));
export const EventCheckInStationPage = lazy(() => import("./features/events/EventCheckInStationPage").then((m) => ({ default: m.EventCheckInStationPage })));
export const KioskStationPage = lazy(() => import("./features/kiosk/KioskStationPage").then((m) => ({ default: m.KioskStationPage })));
export const PublicStatsPage = lazy(() => import("./features/stats/PublicStatsPage").then((m) => ({ default: m.PublicStatsPage })));
export const PublicStatsTvPage = lazy(() => import("./features/stats/PublicStatsTvPage").then((m) => ({ default: m.PublicStatsTvPage })));
export const PublicHandlePage = lazy(() => import("./features/publicPages/PublicHandlePage").then((m) => ({ default: m.PublicHandlePage })));
export const PublicEventCodePage = lazy(() => import("./features/events/PublicEventCodePage").then((m) => ({ default: m.PublicEventCodePage })));
export const PayLinkPage = lazy(() => import("./features/finance/PayLinkPage").then((m) => ({ default: m.PayLinkPage })));
export const PresenceNowPage = lazy(() => import("./features/presence/PresenceNowPage").then((m) => ({ default: m.PresenceNowPage })));
export const PublicWebsiteDetailPage = lazy(() => import("./features/events/PublicWebsiteDetailPage").then((m) => ({ default: m.PublicWebsiteDetailPage })));
export const HostingRequestPage = lazy(() => import("./features/hosting/HostingRequestPage").then((m) => ({ default: m.HostingRequestPage })));
export const HostingInvitePage = lazy(() => import("./features/hosting/HostingInvitePage").then((m) => ({ default: m.HostingInvitePage })));
export const HostingRequestStatusPage = lazy(() => import("./features/hosting/HostingRequestStatusPage").then((m) => ({ default: m.HostingRequestStatusPage })));
// L22: the per-space shop and a buyer's shop orders.
export const PublicShopPage = lazy(() => import("./features/shop/PublicShopPage").then((m) => ({ default: m.PublicShopPage })));
export const PublicShopProductPage = lazy(() => import("./features/shop/PublicShopProductPage").then((m) => ({ default: m.PublicShopProductPage })));
export const ShopOrderStatusPage = lazy(() => import("./features/shop/ShopOrderStatusPage").then((m) => ({ default: m.ShopOrderStatusPage })));
export const MemberShopOrdersPage = lazy(() => import("./features/members/shopOrders/MemberShopOrdersPage").then((m) => ({ default: m.MemberShopOrdersPage })));
export const MfaAccountPage = lazy(() => import("./features/auth/MfaAccountPage").then((m) => ({ default: m.MfaAccountPage })));
export const NotMePage = lazy(() => import("./features/auth/NotMePage").then((m) => ({ default: m.NotMePage })));
export const StaffInvitationAcceptPage = lazy(() => import("./features/auth/StaffInvitationAcceptPage").then((m) => ({ default: m.StaffInvitationAcceptPage })));
export const BookingStaffInvitePage = lazy(() => import("./features/staff/BookingStaffInvitePage").then((m) => ({ default: m.BookingStaffInvitePage })));
export const EventStaffInvitePage = lazy(() => import("./features/staff/EventStaffInvitePage").then((m) => ({ default: m.EventStaffInvitePage })));
export const ProgrammeRoutes = lazy(() => import("./features/events/programme/ProgrammeRoutes").then(m => ({ default: m.ProgrammeRoutes })));
export const CardRoutes = lazy(() => import("./features/cards/CardRoutes").then(m => ({ default: m.CardRoutes })));
export const MemberEventAddonRoutes = lazy(() => import("./features/events/eventAddons/MemberEventAddonRoutes").then(m => ({ default: m.MemberEventAddonRoutes })));
export const DonationRoutes = lazy(() => import("./features/donations/DonationRoutes").then(m => ({ default: m.DonationRoutes })));
