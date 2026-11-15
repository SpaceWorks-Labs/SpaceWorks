import { createHash } from "node:crypto";
import ts from "typescript";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { ROOT, routeInventory, source, sourceFiles } from "./source.census-D12";
import { BOOTSTRAP, PHASES, USER } from "./fetch.census-D12";
import { EXEMPTIONS } from "./contracts.census-D12";
import { emptyResponse } from "./schema.census-D12";
import { RETRY_DEFECTS } from "./retryDefects.census-D12";
import { STATE_DEFECTS } from "./stateDefects.census-D12";
import { stateCopyFor } from "./presentation.census-D12";

const routes = routeInventory();
const semantic = routes.map(({ file, pattern, screen, mode, leaves, platform, memberTab }) =>
  [file, pattern, screen, mode, leaves ?? [], platform ?? false, memberTab ?? ""])
  .sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));

describe("D12 source-derived route and exemption drift guards", () => {
  it("resolves actual filesystem assets independently of the jsdom HTTP origin", () => {
    expect(existsSync(resolve(ROOT, "src/App.tsx"))).toBe(true);
    expect(existsSync(resolve(ROOT, "openapi-schema.json"))).toBe(true);
  });
  it("pins every JSX route, mapped route, conditional element and staff-registry screen", () => {
    expect(routes).toHaveLength(706);
    expect(new Set(routes.map(row => row.id)).size).toBe(706);
    expect(new Set(routes.map(row => row.pattern)).size).toBe(432);
    expect(createHash("sha256").update(JSON.stringify(semantic)).digest("hex"))
      .toBe("fce32452d451368bc3e8b92e93bd4019b3c667e62524445c067d33c523106a53");
  });
  it("requires every staff screen to have a source-derived mounted-leaf obligation", () => {
    expect(routes.filter(row => row.leaves?.length === 0).map(row => row.id)).toEqual([]);
  });
  it("uses actual lazy exports and excludes tabs the single-tenant access predicate refuses", () => {
    expect(routes.filter(row => row.pattern.endsWith("/print")).map(row => row.screen))
      .toEqual(["PrintRequestAlias", "PrintRequestAlias"]);
    expect(routes.filter(row => row.screen === "StaffApp/email-logs").map(row => row.leaves))
      .toEqual(Array.from({ length: 5 }, () => ["DeliveryLogPanel"]));
    expect(routes.filter(row => row.mode === "single" && ["StaffApp/organized", "StaffApp/organizations", "StaffApp/organization-analytics"].includes(row.screen))).toEqual([]);
  });
  it("fills opaque JSON collections from the declared client type without null array fixtures", () => {
    const profile = emptyResponse("/member/profile");
    expect(profile.status).toBe(200);
    expect(profile.body).toMatchObject({ education: [], links: [], projects: [], skills: [] });
    // A survey is read by its event token: absence is the enumeration-safe 404, never a zero survey.
    expect(emptyResponse("/public/lab/events/d12/feedback")).toEqual({ status: 404, body: { code: "not_found", detail: "Census record not found." } });
  });
  it("keeps DRF page envelopes and a blank platform legal projection faithful to their server contracts", () => {
    for (const path of ["/public/makerspaces", "/public/lab/inventory/categories", "/public/lab/spaces", "/admin/makerspaces/1/member-cards"])
      expect(emptyResponse(path)).toEqual({ status: 200, body: { count: 0, next: null, previous: null, results: [] } });
    expect(emptyResponse("/discover/legal/privacy")).toMatchObject({ status: 200, body: { source: "platform", markdown: "", slug: "privacy" } });
  });
  it("requires a live route, concrete product source and exact fix for every retry defect", () => {
    const defects = [...RETRY_DEFECTS, ...STATE_DEFECTS];
    expect(new Set(defects.map(defect => defect.id)).size).toBe(20);
    for (const defect of defects) {
      expect(routes.some(row => "screen" in defect ? row.screen === defect.screen : row.leaves?.includes(defect.leaf))).toBe(true);
      expect(existsSync(resolve(ROOT, "src", defect.source.split(":")[0]))).toBe(true);
      expect(defect.fix.trim()).not.toBe("");
    }
  });
  it("reads actual error/absence copy through named re-exports and query-derived locals", () => {
    const payout = routes.find(row => row.screen === "EventPayoutPage")!;
    expect(stateCopyFor(payout, "error")).toContain("Payout history could not be loaded.");
    expect(stateCopyFor(payout, "empty")).toContain("You have no approved reimbursements yet.");
    expect(stateCopyFor(routes.find(row => row.screen === "TeamJourney")!, "empty"))
      .toContain("Your team must be ready before this step.");
  });
  it("refuses a new router-construction mechanism until the census supports it", () => {
    const unknown: string[] = [];
    for (const file of sourceFiles()) {
      const sf = source(file);
      const walk = (node: ts.Node) => {
        if (ts.isCallExpression(node) && /^(createBrowserRouter|createHashRouter|useRoutes|createRoutesFromElements)$/.test(node.expression.getText()))
          unknown.push(`${file}:${sf.getLineAndCharacterOfPosition(node.getStart()).line + 1}`);
        ts.forEachChild(node, walk);
      };
      walk(sf);
    }
    expect(unknown).toEqual([]);
  });
  it("requires an applicable live route and a written reason for every exemption", () => {
    for (const [key, phases] of Object.entries(EXEMPTIONS)) {
      const [screen, ...pattern] = key.split(":");
      expect(routes.filter(row => row.screen === screen && (!pattern.length || row.pattern === pattern.join(":"))).length).not.toBe(0);
      for (const [phase, reason] of Object.entries(phases)) {
        expect(PHASES).toContain(phase);
        expect(typeof reason).toBe("string"); expect(reason?.trim()).not.toBe("");
      }
    }
  });
  it("keeps admission fixtures tied to the real module, capability and action vocabularies", () => {
    expect(BOOTSTRAP.modules).toContain("member_accounts");
    expect(BOOTSTRAP.features).toContain("loans.enabled");
    expect(USER.staff_roles[0].actions).toContain("manage_makerspace");
  });
});
