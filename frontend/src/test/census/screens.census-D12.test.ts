import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ROOT, routeInventory } from "./source.census-D12";
import { installFetch, REFUSALS } from "./fetch.census-D12";
import { emptyResponse } from "./schema.census-D12";
import { exportedSources } from "./exports.census-D12";
import { SCREEN_COPY, EMPTY_FORMS, PENDING_COPY } from "./screenContracts.census-D12";
import { parseProgrammeContext } from "../../features/events/contracts/parsers";
import { CONTEXTLESS, contextlessExemption } from "./contextless.census-D12";

afterEach(() => vi.unstubAllGlobals());
describe("D12 per-screen driver contracts", () => {
  it("limits missing-tenant state exemptions to central aliases with no slug", () => {
    const routes = routeInventory();
    for (const contract of CONTEXTLESS) {
      const source = readFileSync(resolve(ROOT, "src", contract.source), "utf8");
      expect(source).toContain(contract.guard);
      // The unavailable-here sentence the census asserts is the screen's own Lingui source string.
      const noticeSource = contract.noticeSource ? readFileSync(resolve(ROOT, "src", contract.noticeSource), "utf8") : source;
      if (contract.notice) expect(noticeSource).toContain(`t\`${contract.notice}\``);
      const variants = routes.filter(row => row.screen === contract.screen);
      expect(variants.some(row => contextlessExemption(row, "error") !== undefined)).toBe(true);
      expect(variants.some(row => row.mode === "single" || row.pattern.includes(":slug"))).toBe(true);
      for (const row of variants) if (row.mode === "single" || row.pattern.includes(":slug"))
        expect(contextlessExemption(row, "error")).toBeUndefined();
      for (const row of variants.filter(row => row.screen === "MemberShopOrdersPage" && row.pattern.includes(":orderId")))
        expect(contextlessExemption(row, "error")).toBeUndefined();
    }
  });
  it("keeps each explicit presentation witness tied to its real screen source", () => {
    const routes = routeInventory();
    for (const entry of [...SCREEN_COPY, ...PENDING_COPY]) {
      expect(routes.some(row => row.screen === entry.screen)).toBe(true);
      const source = readFileSync(resolve(ROOT, "src", entry.source), "utf8");
      if (entry.screen === "StaffApp/platform-access") {
        expect(source).toContain('No account is called "${username}".');
        expect(entry.text).toBe('No account is called "d12-operator".');
      } else if (entry.screen === "JobRequestPage" && entry.phase === "module") {
        expect(source).toContain("${displayName} isn't taking job requests right now.");
        expect(entry.text).toBe("D12 Lab isn't taking job requests right now.");
      } else if (entry.screen === "CardVerifyPage" && entry.phase === "permission") {
        expect(entry.text).toBe(REFUSALS.permission.detail);
        expect(readFileSync(resolve(ROOT, "src/features/cards/CardVerifyPage.tsx"), "utf8")).toContain("check.error.message");
      } else expect(source).toContain(entry.text);
    }
    for (const entry of EMPTY_FORMS) {
      expect(entry.reason.trim()).not.toBe("");
      expect(readFileSync(resolve(ROOT, "src", entry.source), "utf8")).toContain(entry.name);
      expect(routes.some(row => "leaf" in entry ? row.leaves?.includes(entry.leaf) : row.screen === entry.screen)).toBe(true);
    }
  });
  it("keeps optional collection projections valid for the member dashboard", () => {
    expect(emptyResponse("/member/makerspaces/1/activity")).toMatchObject({
      status: 200, body: { bookings: { upcoming: [], past: [] }, active_hardware_loans: [], notices: [] },
    });
  });
  it("supplies an exact parseable empty programme context without advertising commands", () => {
    const response = emptyResponse("/public/event-programmes/11111111-1111-4111-8111-111111111111/context");
    expect(response.status).toBe(200);
    const context = parseProgrammeContext(response.body);
    expect(context.eligibility).toEqual({ eligible: false, reason: null });
    expect(Object.entries(context.routes).filter(([key]) => !["member_base", "context"].includes(key))
      .every(([, route]) => route === null)).toBe(true);
  });
  it("follows the requested lazy export without reading other lazy panels", () => {
    const sources = exportedSources(resolve(ROOT, "src/features/staff/StaffTabLoaders.tsx"), "GrantedEventsPanel");
    expect(sources.map(source => source.fileName.replace(/\\/g, "/").split("/src/")[1]))
      .toEqual(["features/staff/GrantedEventsPanel.tsx"]);
  });
  it("classifies a sibling panel's query as domain traffic while preserving ancestor admission", async () => {
    const row = routeInventory().find(row => row.screen === "StaffApp/payments")!;
    const owners = new Set(["App", "StaffApp", "PaymentsPanel"]);
    const network = installFetch("permission", false, row, () => true, () => owners);
    try {
      const result = await fetch("/api/v1/admin/makerspace/1/payments/");
      expect(result.status).toBe(403);
      expect(await result.json()).toEqual(REFUSALS.permission);
      expect(network.domain()).toHaveLength(1);
      owners.delete("PaymentsPanel");
      const admission = await fetch("/api/v1/admin/makerspaces/1/");
      expect(admission.status).toBe(200);
      expect((await admission.json()).slug).toBe("lab");
      expect(network.domain()).toHaveLength(1);
      expect(network.fixtureErrors).toEqual([]);
    } finally { network.dispose(); }
    // A provider-level owner chain (outside App) defers to the committed tree.
    const cold = installFetch("permission", false, row, () => false, () => new Set(["TenantProvider", "QueryClientProvider"]));
    try {
      expect((await fetch("/api/v1/admin/makerspaces/1/")).status).toBe(200);
      expect(cold.domain()).toEqual([]);
    } finally { cold.dispose(); }
  });
  it("never counts a provider-chain request after mount as the screen's own traffic", async () => {
    const row = routeInventory().find(row => row.screen === "StaffApp/payments")!;
    const owners = new Set(["TenantProvider", "QueryClientProvider"]);
    const mounted = installFetch("permission", false, row, () => true, () => owners);
    try {
      // The target is mounted, so the request still gets the phase's answer...
      const provider = await fetch("/api/v1/admin/makerspace/1/payments/");
      expect(provider.status).toBe(403);
      expect(await provider.json()).toEqual(REFUSALS.permission);
      expect(mounted.domain().map(exchange => exchange.outside)).toEqual([true]);
      // ...but it can never satisfy "the screen sent its own request".
      expect(mounted.own()).toEqual([]);
      // A request with no render owner (a mutation or an effect) still counts once the target is mounted.
      owners.clear();
      const effect = installFetch("permission", false, row, () => true, () => undefined);
      try {
        expect((await fetch("/api/v1/admin/makerspace/1/payments/")).status).toBe(403);
        expect(effect.own().map(exchange => exchange.path)).toEqual(["/admin/makerspace/1/payments"]);
      } finally { effect.dispose(); }
      // An App-rooted chain that names the target is its own request.
      const app = installFetch("permission", false, row, () => true, () => new Set(["App", "StaffApp", "PaymentsPanel"]));
      try {
        expect((await fetch("/api/v1/admin/makerspace/1/payments/")).status).toBe(403);
        expect(app.own()).toHaveLength(1);
      } finally { app.dispose(); }
      expect(mounted.fixtureErrors).toEqual([]);
    } finally { mounted.dispose(); }
  });
});
