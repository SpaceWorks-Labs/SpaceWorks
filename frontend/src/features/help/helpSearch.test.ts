import { describe, expect, it } from "vitest";
import { ANONYMOUS_READER, readerFromUser, visibleArticles } from "./helpAudience";
import { helpArticles } from "./helpContent";
import { searchHelp } from "./helpSearch";

const articles = helpArticles();

describe("help search", () => {
  it("returns only articles the reader may see", () => {
    const visible = visibleArticles(articles, ANONYMOUS_READER);
    for (const query of ["refund", "issue photo", "stocktake", "restore", "technician", "rotate key", "cash up"]) {
      const results = searchHelp(visible, query);
      for (const article of results) expect(visible).toContain(article);
      for (const article of results) expect(["member", "organisation"]).toContain(article.section);
    }
    expect(searchHelp(visible, "stocktake")).toEqual([]);
  });

  it("finds a staff article for a reader holding the role", () => {
    const inventory = readerFromUser({
      username: "im", email_verified: true, role: "staff", is_superuser: false, must_change_password: false,
      makerspaces: [{ id: 1, slug: "t", role: null, role_id: null, role_ids: [], role_slugs: [], role_names: [], role_name: "",
        role_slug: null, source: "membership", actions: ["edit_inventory", "accept_request"], can_configure_machine_types: false,
        is_machine_only: false, can_refer: false, can_verify: false, verified_at: null, referrals_enabled: false }],
    });
    const results = searchHelp(visibleArticles(articles, inventory), "stocktake");
    expect(results[0]?.id).toBe("inventory-manager/stocktake-and-transfers");
  });

  it("ranks title matches first, needs every word, and ignores an empty query", () => {
    const results = searchHelp(articles, "borrow tools");
    expect(results[0]?.id).toBe("member/borrow-tools");
    expect(searchHelp(articles, "   ")).toEqual([]);
    expect(searchHelp(articles, "borrow zzzzqx")).toEqual([]);
  });
});
