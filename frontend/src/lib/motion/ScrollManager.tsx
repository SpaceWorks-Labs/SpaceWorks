import { useLayoutEffect, useRef } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

const STORE_KEY = "spaceworks.scroll.v1";
const MAX_ENTRIES = 50;

type Positions = Record<string, number>;

function readPositions(): Positions {
  try {
    const raw = window.sessionStorage.getItem(STORE_KEY);
    return raw ? (JSON.parse(raw) as Positions) : {};
  } catch { return {}; }
}

function savePosition(key: string, y: number) {
  try {
    const positions = readPositions();
    delete positions[key];
    positions[key] = y;
    const keys = Object.keys(positions);
    for (const old of keys.slice(0, Math.max(0, keys.length - MAX_ENTRIES))) delete positions[old];
    window.sessionStorage.setItem(STORE_KEY, JSON.stringify(positions));
  } catch { /* private mode or full storage: back/forward just starts at the top */ }
}

function scrollToHash(hash: string) {
  const id = decodeURIComponent(hash.slice(1));
  const target = id ? document.getElementById(id) : null;
  if (target) target.scrollIntoView({ block: "start" });
  else window.scrollTo({ top: 0, left: 0, behavior: "instant" });
}

/**
 * Mount once inside the router. A new page always opens at the top (the browser would otherwise keep
 * the previous page's scroll, e.g. halfway down the landing story). Back and forward return to where
 * that page was left. A link to `#section` scrolls to the section. A change of only the query string
 * (filters, tabs kept in the URL) keeps the current position.
 */
export function ScrollManager() {
  const location = useLocation();
  const navigationType = useNavigationType();
  const previous = useRef({ key: location.key, pathname: location.pathname });

  useLayoutEffect(() => {
    if ("scrollRestoration" in window.history) window.history.scrollRestoration = "manual";
  }, []);

  useLayoutEffect(() => {
    const from = previous.current;
    if (from.key === location.key) return;
    savePosition(from.key, window.scrollY);
    previous.current = { key: location.key, pathname: location.pathname };
    if (navigationType === "POP") {
      const saved = readPositions()[location.key];
      window.scrollTo({ top: saved ?? 0, left: 0, behavior: "instant" });
      return;
    }
    if (location.hash) { scrollToHash(location.hash); return; }
    if (from.pathname !== location.pathname) window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  }, [location.key, location.pathname, location.hash, navigationType]);

  return null;
}
