import { API_V1_URL, memberRequest } from "../../../lib/api";

// Hand-written mirrors of the feed routes (lane L18 `events/views_calendar_feeds_r2.py` and the
// existing booking feed in `bookings/views_feed.py`).
export type FeedState = { enabled: boolean; token_hint: string | null; created_at?: string | null; rotated_at?: string | null };
export type IssuedFeed = { feed_url: string; token_hint: string };
export type PersonalKind = "shifts" | "combined";

const personal = (makerspaceId: number, kind: PersonalKind) => `/member/makerspaces/${makerspaceId}/calendar-feeds/${kind}/`;
const booking = (slug: string) => `/public/${encodeURIComponent(slug)}/my-bookings/calendar/`;

export type FeedEndpoint = { key: readonly unknown[]; state: () => Promise<FeedState>; issue: () => Promise<IssuedFeed>;
  revoke: () => Promise<void> };

export function personalFeed(makerspaceId: number, kind: PersonalKind): FeedEndpoint {
  const path = personal(makerspaceId, kind);
  return {
    key: ["member-calendar-feed", makerspaceId, kind],
    state: () => memberRequest<FeedState>(path),
    issue: () => memberRequest<IssuedFeed>(path, { method: "POST", body: JSON.stringify({}) }),
    revoke: () => memberRequest<void>(path, { method: "DELETE" }),
  };
}

export function bookingFeed(slug: string): FeedEndpoint {
  const path = booking(slug);
  return {
    key: ["member-calendar-feed", slug, "bookings"],
    state: () => memberRequest<FeedState>(path),
    issue: () => memberRequest<IssuedFeed>(path, { method: "POST" }),
    revoke: () => memberRequest<void>(path, { method: "DELETE" }),
  };
}

/** The public listed-events calendar: no token, anyone may subscribe. */
export function publicEventsFeedUrl(slug: string) {
  const base = API_V1_URL.startsWith("http") ? API_V1_URL : `${window.location.origin}${API_V1_URL}`;
  return `${base}/public/${encodeURIComponent(slug)}/events-calendar.ics`;
}
