import { runtimeTenantConfig } from "../../lib/runtimeConfig";
import { createContext, useContext, useSyncExternalStore, type ReactNode } from "react";

/** `patch` marks mascot art; `still` replaces an animated file under reduced motion; `frames` marks a horizontal sprite sheet. */
export type DelightSource = { light: string; dark: string; patch?: boolean; still?: string; frames?: number };
export type DelightArtwork = Partial<Record<"loader" | "welcome" | "success" | "waiting" | "empty" | "error" | "tag" | "companionWalk" | "companionFollow" | "companionNap" | "companionPrint" | "demo", DelightSource>>;
export type DelightPolicy = { enabled: boolean; eggsEnabled: boolean; artwork: DelightArtwork };
const Policy = createContext<DelightPolicy | null>(null);
function runtimePolicy() {
  const runtime = runtimeTenantConfig();
  return { enabled: runtime.uiDelightEnabled === true, eggsEnabled: runtime.uiEasterEggsEnabled === true };
}

/** G passes runtime flags and ARTWORK's manifest here when mounting the shell. */
export function DelightProvider({ children, enabled, eggsEnabled, artwork = {} }: Partial<DelightPolicy> & { children: ReactNode }) {
  const runtime = runtimePolicy();
  return <Policy.Provider value={{ enabled: enabled ?? runtime.enabled, eggsEnabled: eggsEnabled ?? runtime.eggsEnabled, artwork }}>{children}</Policy.Provider>;
}

export function useDelight(): DelightPolicy {
  const policy = useContext(Policy);
  return policy ?? { ...runtimePolicy(), artwork: {} };
}

const query = "(prefers-reduced-motion: reduce)";
function subscribe(change: () => void) {
  const media = window.matchMedia?.(query);
  media?.addEventListener("change", change);
  return () => media?.removeEventListener("change", change);
}
export function useReducedMotion() {
  return useSyncExternalStore(subscribe, () => window.matchMedia?.(query).matches ?? true, () => true);
}

export function eggsAllowed(path: string) {
  const segments = path.toLowerCase().split(/[/?#_=&-]+/);
  return !segments.some(part => ["kiosk", "scanner", "scan", "checkin", "check", "checkout", "payment", "payments", "pay"].includes(part));
}
