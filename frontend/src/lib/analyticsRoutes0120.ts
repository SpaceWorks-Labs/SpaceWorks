/** Public pages added in 0.12.0 that may count page views (route templates only, never real paths). */
export const analyticsPublicRoutes0120 = [
  "/features", "/features/:module", "/spaces", "/discover", "/organizations",
  "/docs", "/docs/*",
  "/help", "/help/:sectionId", "/help/:sectionId/:articleSlug",
  "/m/:slug/help", "/m/:slug/help/:sectionId", "/m/:slug/help/:sectionId/:articleSlug",
  "/now", "/m/:slug/now",
];

/** Never analytics or replay: shared screens with no visitor to ask for consent. */
export const analyticsExcludedScreens = ["/display", "/stats/tv", "/m/:slug/stats/tv",
  // Decision 361: GitHub's native sign-in return carries a one-time code; never observed.
  "/app/auth/github/callback"];
