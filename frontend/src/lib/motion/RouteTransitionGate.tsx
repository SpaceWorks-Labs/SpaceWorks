import { useLayoutEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { replayRouteEnter, routeDirection, settleRouteTransition } from "./routeTransition";

/**
 * Mount once inside the router. When a new location has rendered it releases the waiting View
 * Transition; if none was waiting (back/forward buttons, links we do not wrap, a slow chunk) it
 * plays the CSS fade-in on the content region instead, so every page change moves the same way.
 */
export function RouteTransitionGate() {
  const { pathname } = useLocation();
  const previous = useRef(pathname);
  useLayoutEffect(() => {
    const from = previous.current;
    previous.current = pathname;
    const covered = settleRouteTransition();
    if (from === pathname || covered) return;
    replayRouteEnter(routeDirection(from, pathname));
  }, [pathname]);
  return null;
}
