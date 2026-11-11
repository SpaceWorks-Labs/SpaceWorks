import type { Makerspace } from "../../../types/inventory";

/** DRF page size, the standing list convention; the public directory is one unpaginated array, paged here. */
export const SPACES_PAGE_SIZE = 24;
export type SpacesSort = "name" | "-name";
export type SpacesFilter = { query: string; place: string; sort: SpacesSort };

export function normalizeSearch(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, " ");
}

function searchText(space: Makerspace) {
  return normalizeSearch([space.name, space.public_code, space.slug, space.location].filter(Boolean).join(" "));
}

/** Distinct, trimmed place names in A-Z order; the place filter only appears when there are two or more. */
export function placesOf(spaces: readonly Makerspace[]) {
  const seen = new Map<string, string>();
  for (const space of spaces) {
    const place = space.location?.trim();
    if (place && !seen.has(place.toLowerCase())) seen.set(place.toLowerCase(), place);
  }
  return [...seen.values()].sort((a, b) => a.localeCompare(b));
}

/** Every search word must match the name, code, slug or place; the place filter is an exact, case-blind match. */
export function filterSpaces(spaces: readonly Makerspace[], { query, place, sort }: SpacesFilter) {
  const tokens = normalizeSearch(query).split(" ").filter(Boolean);
  const placeKey = place.trim().toLowerCase();
  const matches = spaces.filter(space => {
    if (placeKey && space.location?.trim().toLowerCase() !== placeKey) return false;
    const text = searchText(space);
    return tokens.every(token => text.includes(token));
  });
  const sorted = [...matches].sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));
  return sort === "-name" ? sorted.reverse() : sorted;
}

export function pageOf<T>(items: readonly T[], page: number) {
  const last = Math.max(1, Math.ceil(items.length / SPACES_PAGE_SIZE));
  const current = Math.min(Math.max(1, page), last);
  return { page: current, items: items.slice((current - 1) * SPACES_PAGE_SIZE, current * SPACES_PAGE_SIZE) };
}
