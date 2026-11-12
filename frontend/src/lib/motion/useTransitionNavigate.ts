import { useCallback } from "react";
import { useNavigate, type NavigateOptions, type To } from "react-router-dom";
import { canTransitionRoute, navigateWithTransition } from "./routeTransition";

const hrefOf = (to: To) => typeof to === "string" ? to : `${to.pathname ?? ""}${to.search ?? ""}${to.hash ?? ""}`;

/**
 * Drop-in for `useNavigate` whose pushes use a View Transition. Replace-navigations (redirects,
 * URL-state sync), history deltas and same-page changes pass straight through to the router.
 */
export function useTransitionNavigate() {
  const navigate = useNavigate();
  return useCallback(((to: To | number, options?: NavigateOptions) => {
    if (typeof to === "number") { navigate(to); return; }
    if (options?.replace) { navigate(to, options); return; }
    const from = `${window.location.pathname}${window.location.search}`;
    const target = hrefOf(to);
    if (!canTransitionRoute(from, target)) { navigate(to, options); return; }
    navigateWithTransition(() => navigate(to, options), from, target);
  }) as ReturnType<typeof useNavigate>, [navigate]);
}
