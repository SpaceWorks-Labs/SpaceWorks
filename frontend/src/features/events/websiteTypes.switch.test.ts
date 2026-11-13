import { describe, expect, it } from "vitest";
import { sponsorTierLabel } from "./websiteTypes";

describe("sponsorTierLabel", () => {
  it.each([
    ["platinum", "Platinum"],
    ["gold", "Gold"],
    ["silver", "Silver"],
    ["partner", "Partner"],
    ["community_partner", "Community partner"],
  ])("%s reads %s", (code, text) => expect(sponsorTierLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(sponsorTierLabel("zz_unknown_code")).toBe("zz unknown code"));
});

