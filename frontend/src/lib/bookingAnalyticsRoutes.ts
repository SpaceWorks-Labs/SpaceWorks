/** Public booking adapter for the shared manual analytics policy.
 * Private confirmations, feeds, grant invites and scanners stay outside this list.
 * BK-F detail pages must use these paths without credentials in navigation URLs.
 */
export const bookingAnalyticsRoutes = [
  "/bookings", "/bookings/:resourceToken",
  "/m/:slug/bookings", "/m/:slug/bookings/:resourceToken",
];
