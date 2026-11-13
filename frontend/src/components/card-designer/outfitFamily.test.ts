// Decision 220(c): the designers name the brand text face Outfit; a stored legacy "Gilroy"
// (old revisions, imports, tenant dumps) still loads and shows as Outfit.
import { describe, expect, it } from "vitest";
import { brandFamily } from "../../features/staff/eventCredentials/layout";
import { canonicalFamily, cssFamily } from "./fontLoader";
import { newLayer } from "./designDocument";

describe("Outfit family", () => {
  it("reads legacy Gilroy as Outfit in the card designer", () => {
    expect(canonicalFamily("Gilroy")).toBe("Outfit");
    expect(canonicalFamily("Lato")).toBe("Lato");
    expect(cssFamily("Gilroy")).toBe(cssFamily("Outfit"));
  });

  it("starts new card text layers in Outfit", () => {
    const side = { page_width_mm: 85.6, page_height_mm: 53.98, layers: [] } as never;
    expect(newLayer("text", side, "cr80-landscape").font_family).toBe("Outfit");
  });

  it("shows certificate and badge layers as Outfit or Unbounded", () => {
    expect(brandFamily({ font_family: "Gilroy" })).toBe("Outfit");
    expect(brandFamily({})).toBe("Outfit");
    expect(brandFamily({ font_family: "Unbounded" })).toBe("Unbounded");
  });
});
