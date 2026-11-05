import { useQuery } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { staffRequest } from "../../lib/api/requests";
import type { SessionContext } from "../../lib/api/sessionContext";
import { readStorage, writeStorage } from "../../lib/safeStorage";

export type NoticeAnnouncement = { id: number; title: string; body: string; severity: "info" | "maintenance" | "policy" | "warning";
  starts_at: string; ends_at: string | null; makerspace_ids: number[] };
export type NoticeSpace = { id: number; name: string; slug: string; state: "read_only" | "suspended"; reason: string; since: string };
export type PlatformNotices = { announcements: NoticeAnnouncement[]; spaces: NoticeSpace[] };

export const READ_ONLY_LEAD = "This space is read-only: you can view and export, but nothing new can be created.";

/** Live announcements and the caller's read-only/paused spaces; every signed-in surface reads this. */
export function usePlatformNotices(enabled: boolean, context: SessionContext) {
  return useQuery({
    queryKey: ["platform-notices", context],
    queryFn: () => staffRequest<PlatformNotices>("/platform-notices", {}, context),
    enabled,
    refetchInterval: 5 * 60_000,
    staleTime: 60_000,
    retry: false,
  });
}

/** The space's notice, matched by id when the caller knows it, else by slug. */
export function spaceNotice(data: PlatformNotices | undefined, space: { id?: number; slug?: string }) {
  return data?.spaces.find(row => (space.id !== undefined && row.id === space.id) || (Boolean(space.slug) && row.slug === space.slug));
}

const DISMISSED_KEY = "spaceworks.platformNotices.dismissed";
const listeners = new Set<() => void>();

function readDismissed(): number[] {
  try {
    const value = JSON.parse(readStorage(DISMISSED_KEY, "[]")) as unknown;
    return Array.isArray(value) ? value.filter((item): item is number => typeof item === "number") : [];
  } catch {
    return [];
  }
}

let snapshot = readDismissed().join(",");

/** Dismissed announcement ids, remembered per browser so a dismissed banner stays gone across reloads. */
export function useDismissedAnnouncements() {
  const value = useSyncExternalStore(listener => { listeners.add(listener); return () => { listeners.delete(listener); }; }, () => snapshot);
  const ids = value ? value.split(",").map(Number) : [];
  const dismiss = (id: number) => {
    // Keep the list short: only the most recent dismissals matter, old announcements have ended.
    const next = [...readDismissed().filter(item => item !== id), id].slice(-50);
    writeStorage(DISMISSED_KEY, JSON.stringify(next));
    snapshot = next.join(",");
    listeners.forEach(listener => listener());
  };
  return { ids, dismiss };
}
