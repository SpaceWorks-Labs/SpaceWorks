import { useQuery } from "@tanstack/react-query";

import { apiGet } from "../../lib/api";

export type StatsSectionKey = "events" | "machines" | "printing" | "lending" | "community";
export type PublicStatsVisibility = Record<string, boolean>;
export const publicWidgetVisible = (visibility: PublicStatsVisibility | undefined, key: string) => visibility?.[key] !== false;

/** A published count: `value` is null while it is suppressed (below 3, shown as "fewer than 3"). */
export type PublicCount = { value: number | null; suppressed: boolean };

export type PublicStatsMetric = PublicCount & {
  key: string;
  section: StatsSectionKey;
  label: string;
  kind: "count" | "hours";
};

export type PublicStatsResponse = {
  /** Shown sections, in the order the Space Manager chose (#170). */
  sections: StatsSectionKey[];
  period: { key: "month" | "year" | "all" | "fy"; label: string; start: string | null; end: string | null };
  headline: PublicStatsMetric[];
  metrics: PublicStatsMetric[];
  tv: { enabled: boolean; refresh_seconds: number };
  machines: { usage_hours: number | null } | null;
  visibility?: PublicStatsVisibility;
  printing: PublicStatsPrinting | null;
  hardware: PublicStatsHardware | null;
  current_loans: PublicStatsCurrentLoan[] | null;
  events: PublicStatsEvents | null;
  community: PublicStatsCommunity | null;
};

export type PublicStatsEvents = {
  upcoming: { public_token: string; title: string; starts_at: string; ends_at: string; image_url: string | null }[];
  upcoming_count: PublicCount | null;
  held: PublicCount | null;
  attendees: PublicCount | null;
};

export type PublicStatsCommunity = {
  active_members: PublicCount | null;
  new_members: PublicCount | null;
  bookings: PublicCount | null;
  checkins: PublicCount | null;
};

export type PublicStatsPrinting = {
  hours_all_time: number | null;
  hours_this_month: number | null;
  busiest_printer: {
    name: string;
    model: string;
    hours: number;
    completed: number;
    image_url?: string | null;
  } | null;
  per_printer: {
    name: string;
    model: string;
    jobs: number;
    hours: number;
    grams: number;
    image_url?: string | null;
  }[];
  grams_all_time: number | null;
  by_brand: { brand: string; grams: number }[];
  jobs: {
    completed: number | null;
    status_counts: {
      pending: number;
      accepted: number;
      printing: number;
      completed: number | null;
      collected: number;
      failed: number;
      rejected: number;
      cancelled?: number;
    } | null;
    queue: {
      pending: number;
      accepted: number;
      printing: number;
    } | null;
  };
  filament_trend: { period: string; grams: number }[];
};

export type PublicStatsHardware = {
  most_popular: {
    name: string;
    times_lent: number;
    total_quantity_lent: number;
  }[];
  tools_out: { name: string; quantity_out: number }[];
  library: {
    currently_out_count: number | null;
    library_size: number | null;
    available_count: number | null;
  };
  recently_added: { name: string; created_at: string }[];
};

export type PublicStatsCurrentLoan = {
  item_name: string;
  holder_name: string;
  due: string | null;
  since: string | null;
};

export const publicStatsKey = (slug: string) => ["public-stats", slug] as const;

export async function fetchPublicStats(
  slug: string,
): Promise<PublicStatsResponse> {
  return apiGet<PublicStatsResponse>(`/public/${slug}/stats/`);
}

/** `refetchSeconds` drives the TV mode's auto-refresh; the page itself fetches once. */
export function usePublicStats(slug: string, refetchSeconds?: number) {
  return useQuery({
    queryKey: publicStatsKey(slug),
    queryFn: () => fetchPublicStats(slug),
    enabled: Boolean(slug),
    refetchInterval: refetchSeconds ? refetchSeconds * 1000 : false,
    refetchIntervalInBackground: Boolean(refetchSeconds),
  });
}
