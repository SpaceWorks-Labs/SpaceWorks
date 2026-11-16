import { describe, expect, it } from "vitest";
import type { Makerspace } from "../../../types/inventory";
import { SPACES_PAGE_SIZE, filterSpaces, normalizeSearch, pageOf, placesOf } from "./spacesFilter";

const spaces: Makerspace[] = [
  { name: "beta Woodshop", public_code: "UP5U", slug: "beta-wood", location: "North Wing" },
  { name: "Alpha Robotics Lab", public_code: "RQBG", slug: "alpha-lab", location: " Main Campus " },
  { name: "Gamma Fabrication Studio", public_code: "B4T8", slug: "gamma-fab", location: "main campus" },
  { name: "Delta Textiles", public_code: "TX7C", slug: "delta", location: "" },
];
const all = { query: "", place: "", sort: "name" as const };

describe("spaces directory filtering", () => {
  it("normalises search text", () => {
    expect(normalizeSearch("  Wood   SHOP ")).toBe("wood shop");
  });

  it("lists distinct places case-blind, trimmed and sorted", () => {
    expect(placesOf(spaces)).toEqual(["Main Campus", "North Wing"]);
  });

  it("matches every search word against name, code, slug or place", () => {
    expect(filterSpaces(spaces, { ...all, query: "wood" }).map(s => s.slug)).toEqual(["beta-wood"]);
    expect(filterSpaces(spaces, { ...all, query: "rqbg" }).map(s => s.slug)).toEqual(["alpha-lab"]);
    expect(filterSpaces(spaces, { ...all, query: "campus gamma" }).map(s => s.slug)).toEqual(["gamma-fab"]);
    expect(filterSpaces(spaces, { ...all, query: "zeppelin" })).toEqual([]);
  });

  it("filters by place exactly, ignoring case and padding", () => {
    expect(filterSpaces(spaces, { ...all, place: "Main Campus" }).map(s => s.slug)).toEqual(["alpha-lab", "gamma-fab"]);
  });

  it("sorts by name either way, case-blind", () => {
    expect(filterSpaces(spaces, all).map(s => s.name[0].toLowerCase())).toEqual(["a", "b", "d", "g"]);
    expect(filterSpaces(spaces, { ...all, sort: "-name" }).map(s => s.name[0].toLowerCase())).toEqual(["g", "d", "b", "a"]);
  });

  it("pages at the DRF page size and clamps out-of-range pages", () => {
    const many = Array.from({ length: 30 }, (_, i) => i);
    expect(SPACES_PAGE_SIZE).toBe(24);
    expect(pageOf(many, 1).items).toHaveLength(24);
    expect(pageOf(many, 2)).toEqual({ page: 2, items: many.slice(24) });
    expect(pageOf(many, 9).page).toBe(2);
    expect(pageOf([], 3)).toEqual({ page: 1, items: [] });
  });
});
