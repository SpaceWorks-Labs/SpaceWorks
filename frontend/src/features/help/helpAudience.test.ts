import { describe, expect, it } from "vitest";
import type { StaffAuthUser } from "../../lib/api";
import { ANONYMOUS_READER, articleVisible, readerFromUser, visibleArticles, visibleSections } from "./helpAudience";
import { helpArticles } from "./helpContent";
import { HELP_SECTIONS } from "./helpSections";

const STAFF_SECTIONS = ["space-manager", "inventory-manager", "handover", "machine-manager", "technician",
  "booking-manager", "event-manager", "finance", "shop-manager"];
const PLATFORM_SECTIONS = ["superadmin", "host-operator"];

function person(actions: string[], extra: Partial<StaffAuthUser> = {}): StaffAuthUser {
  return {
    username: "reader", email_verified: true, role: "member", is_superuser: false, must_change_password: false,
    kind: "person", makerspaces: actions.length ? [{
      id: 1, slug: "tinkerspace", role: null, role_id: null, role_ids: [], role_slugs: [], role_names: [], role_name: "",
      role_slug: null, source: "membership", actions, can_configure_machine_types: false, is_machine_only: false,
      can_refer: false, can_verify: false, verified_at: null, referrals_enabled: false,
    }] : [],
    ...extra,
  };
}

const articles = helpArticles();
const sectionIds = (actions: string[], extra: Partial<StaffAuthUser> = {}) =>
  visibleSections(articles, readerFromUser(person(actions, extra))).map(section => section.id);

describe("help role gating", () => {
  it("has an article in every section, so every role has a guide", () => {
    for (const section of HELP_SECTIONS) {
      expect(articles.filter(article => article.section === section.id).length, section.id).toBeGreaterThan(0);
    }
  });

  it("never shows a member or a visitor any staff or platform article", () => {
    for (const reader of [ANONYMOUS_READER, readerFromUser(person([]))]) {
      const shown = visibleArticles(articles, reader);
      expect(shown.length).toBeGreaterThan(0);
      for (const article of shown) expect(["member", "organisation"]).toContain(article.section);
      expect(visibleSections(articles, reader).map(section => section.id)).toEqual(["member", "organisation"]);
    }
  });

  it("shows a Technician the Technician section and no unrelated staff section", () => {
    const sections = sectionIds(["work_repairs", "run_maintenance", "set_service_state"]);
    expect(sections).toContain("technician");
    for (const other of ["space-manager", "finance", "inventory-manager", "shop-manager", "superadmin", "host-operator"]) {
      expect(sections).not.toContain(other);
    }
    const technician = readerFromUser(person(["work_repairs"]));
    expect(articles.find(article => article.id === "finance/refunds")).toBeDefined();
    expect(articleVisible(articles.find(article => article.id === "finance/refunds")!, technician)).toBe(false);
  });

  it("gives each built-in role its own section", () => {
    expect(sectionIds(["edit_inventory", "accept_request", "reject_request", "manage_qr"])).toContain("inventory-manager");
    expect(sectionIds(["manage_machines"])).toContain("machine-manager");
    expect(sectionIds(["manage_bookings"])).toContain("booking-manager");
    expect(sectionIds(["manage_events"])).toContain("event-manager");
    expect(sectionIds(["view_finance"])).toContain("finance");
    expect(sectionIds(["manage_shop", "sell_shop", "view_shop"])).toContain("shop-manager");
    expect(sectionIds(["issue_request", "return_request", "collect_service_request"])).toContain("handover");
  });

  it("shows a Space Manager every staff section but not the platform ones", () => {
    const sections = sectionIds(["manage_makerspace", "manage_members", "view_finance"]);
    for (const id of STAFF_SECTIONS) expect(sections).toContain(id);
    for (const id of PLATFORM_SECTIONS) expect(sections).not.toContain(id);
  });

  it("shows the platform superadmin everything, host operator included", () => {
    const sections = sectionIds([], { kind: "platform", is_platform: true });
    expect(sections).toEqual(HELP_SECTIONS.map(section => section.id));
  });

  it("lets a resource grant holder read the assigned-resources article without a role", () => {
    const helper = readerFromUser(person([], { booking_grants: [{ space_id: 1, makerspace_id: 1, makerspace_slug: "t", name: "Laser room", source: "booking_grant", permissions: [] }] }));
    const article = articles.find(item => item.id === "event-manager/assigned-resources")!;
    expect(articleVisible(article, helper)).toBe(true);
    expect(visibleSections(articles, helper).map(section => section.id)).not.toContain("finance");
  });

  it("hides articles a known space cannot use, and shows them when its switch is on", () => {
    const manager = readerFromUser(person(["manage_makerspace"]));
    const shop = articles.find(article => article.id === "shop-manager/set-up-the-shop")!;
    expect(articleVisible(shop, manager, { slug: "t", modules: [], features: [] })).toBe(false);
    expect(articleVisible(shop, manager, { slug: "t", modules: ["shop"], features: [] })).toBe(true);
    expect(articleVisible(shop, manager, null)).toBe(true);
  });
});
