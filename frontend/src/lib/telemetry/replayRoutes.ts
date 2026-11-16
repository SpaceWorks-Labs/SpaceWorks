import { analyticsExcludedScreens } from "../analyticsRoutes0120";
/** Route templates only; authorization and query/hash checks remain in safePage. */
const posthogPublic = new Set(["/", "/m/:slug", "/inventory", "/m/:slug/inventory", "/events", "/m/:slug/events", "/shop", "/m/:slug/shop", "/bookings", "/m/:slug/bookings", "/about"]);
/** Screens no provider may ever replay, whatever an allow-list later admits (decision 361). */
const replayExcluded = new Set(analyticsExcludedScreens);
export function replayRoute(provider: string, template: string | null): boolean {
  if (!template || replayExcluded.has(template)) return false;
  return provider === "posthog" ? posthogPublic.has(template) : provider === "clarity" && template === "/about";
}
