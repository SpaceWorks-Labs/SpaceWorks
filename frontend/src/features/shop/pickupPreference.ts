import { readStorage, removeStorage, writeStorage } from "../../lib/safeStorage";

/**
 * #135 Q-S18 follow-up: an event page's "Get it at this event" link remembers that event in
 * this browser, so the shop checkout opens with event pickup chosen. A display hint only:
 * the server still checks the event when the order is placed.
 */
export type PickupEvent = { id: number; title: string; starts_at: string };

export const PICKUP_EVENT_PARAM = "pickup_event";
const key = (slug: string) => `spaceworks.shop.pickup-event:${slug}`;

export function rememberPickupEvent(slug: string, event: PickupEvent) {
  writeStorage(key(slug), JSON.stringify({ id: event.id, title: event.title, starts_at: event.starts_at }));
}

export function forgetPickupEvent(slug: string) {
  removeStorage(key(slug));
}

export function rememberedPickupEvent(slug: string): PickupEvent | null {
  try {
    const value: unknown = JSON.parse(readStorage(key(slug), "null"));
    if (!value || typeof value !== "object") return null;
    const row = value as PickupEvent;
    return Number.isInteger(row.id) && typeof row.title === "string" && typeof row.starts_at === "string" ? row : null;
  } catch {
    return null;
  }
}

/** The pickup the checkout starts with: a `?pickup_event=` link to a listed event, else the remembered one. */
export function initialPickup(slug: string, listed: readonly PickupEvent[],
  search = window.location.search): { pickup: number | "space"; extra: PickupEvent | null } {
  const fromLink = Number(new URLSearchParams(search).get(PICKUP_EVENT_PARAM));
  const linked = listed.find(row => row.id === fromLink);
  if (linked) return { pickup: linked.id, extra: null };
  const remembered = rememberedPickupEvent(slug);
  if (!remembered) return { pickup: "space", extra: null };
  // An unlisted event (reachable by its link) is not in the shop's own list, so it is offered as an extra choice.
  return { pickup: remembered.id, extra: listed.some(row => row.id === remembered.id) ? null : remembered };
}
