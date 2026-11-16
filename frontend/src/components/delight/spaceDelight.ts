import { useSyncExternalStore } from "react";

/**
 * The features of the makerspace whose screen is showing, for the delight policy.
 *
 * Public and member pages read it from the tenant bootstrap; the staff console has no
 * bootstrap, so its shell publishes the active makerspace here. `null` means no space
 * is known (central directory, landing page), where only the deployment flags apply.
 */
let current: readonly string[] | null = null;
const listeners = new Set<() => void>();

export function setDelightSpaceFeatures(features: readonly string[] | null) {
  if (features === current) return;
  current = features;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useDelightSpaceFeatures() {
  return useSyncExternalStore(subscribe, () => current, () => null);
}

/** A space allows a delight feature unless it has turned it off. */
export function spaceAllows(features: readonly string[] | null | undefined, key: "ui.delight" | "ui.easter_eggs") {
  return features == null || features.includes(key);
}
