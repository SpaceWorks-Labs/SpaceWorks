import { useCallback, useSyncExternalStore } from "react";

/** Choose one responsive slot tree so forms never mount duplicate IDs/controls. */
export function useLayoutMedia(query: string) {
  const subscribe = useCallback((notify: () => void) => {
    const media = window.matchMedia?.(query);
    media?.addEventListener("change", notify);
    return () => media?.removeEventListener("change", notify);
  }, [query]);
  const snapshot = useCallback(() => window.matchMedia?.(query).matches ?? false, [query]);
  return useSyncExternalStore(subscribe, snapshot, () => false);
}
