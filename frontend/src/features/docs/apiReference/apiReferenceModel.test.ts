import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { apiReference } from "../../../../scripts/api-reference-plugin";
import { fixtureSpec } from "./__tests__/apiFixture";
import { buildApiReference, reachableSchemas, slugifyTag } from "./apiReferenceModel";

describe("buildApiReference", () => {
  const ref = buildApiReference(fixtureSpec);

  it("indexes every operation and orders tags by x-tagGroups, then the rest A-Z", () => {
    expect(ref.version).toBe("9.9.9");
    expect(ref.tags.map(tag => [tag.slug, tag.group, tag.count])).toEqual([
      ["loans", "Inventory and loans", 2], ["stock", "Inventory and loans", 1], ["webhooks", "", 1],
    ]);
    expect(ref.tags[0].description).toBe("Borrowing and returns.");
    expect(ref.index).toContainEqual({ tag: "loans", operationId: "loans_create", method: "POST", path: "/api/v1/admin/makerspaces/{makerspace_id}/loans/", summary: "Create a loan" });
    expect(ref.index).toHaveLength(4);
  });

  it("splits by tag and ships only the schemas each tag reaches", () => {
    const loans = ref.payloads.loans;
    expect(loans.operations.map(op => op.operationId)).toEqual(["loans_create", "public_loans_list"]);
    expect(Object.keys(loans.schemas)).toEqual(["Item", "Loan", "LoanRequest", "Problem"]);
    expect(loans.schemas.Unused).toBeUndefined();
    expect(Object.keys(ref.payloads.stock.schemas)).toEqual([]);
    expect(Object.keys(loans.securitySchemes)).toEqual(["PublishableKey", "jwtAuth"]);
  });

  it("keeps auth, notes and small examples, and drops examples bloat", () => {
    const [create, list] = ref.payloads.loans.operations;
    expect(create).toMatchObject({ security: ["jwtAuth"], anonymous: false });
    expect(list).toMatchObject({ security: ["PublishableKey"], anonymous: true });
    expect(ref.payloads.loans.schemas.Problem.examples).toBeUndefined();
    expect((ref.payloads.loans.schemas.Loan.properties as Record<string, { example?: string }>).note.example).toBe("Chuck sticks");
    expect(ref.payloads.stock.operations[0].notes).toMatchObject({ noRequestBody: true, noResponseBody: true });
    expect(ref.payloads.webhooks.operations[0].notes.request).toBe("The provider's callback.");
  });

  it("follows self-referencing schemas without looping", () => {
    expect(Object.keys(reachableSchemas({ $ref: "#/components/schemas/Item" }, fixtureSpec.components.schemas))).toEqual(["Item"]);
  });

  it("makes stable, unique slugs", () => {
    expect(slugifyTag("Card photos (staff)")).toBe("card-photos-staff");
    const spec = { ...fixtureSpec, "x-tagGroups": [], tags: [], paths: {
      "/a/": { get: { operationId: "a", tags: ["A b"], responses: {} } },
      "/b/": { get: { operationId: "b", tags: ["A-b"], responses: {} } },
    } };
    expect(buildApiReference(spec).tags.map(tag => tag.slug)).toEqual(["a-b", "a-b-2"]);
  });
});

describe("apiReference vite plugin", () => {
  it("serves the index, the lazy loaders and one module per tag", () => {
    const dir = mkdtempSync(join(tmpdir(), "api-ref-"));
    writeFileSync(join(dir, "openapi-schema.json"), JSON.stringify(fixtureSpec));
    const plugin = apiReference();
    type Hook = (this: unknown, ...args: unknown[]) => unknown;
    (plugin.configResolved as Hook).call({}, { root: dir });
    const context = { addWatchFile() {}, error(message: string) { throw new Error(message); } };
    const load = (id: string) => (plugin.load as Hook).call(context, (plugin.resolveId as Hook).call(context, id)) as string;
    expect((plugin.resolveId as Hook).call(context, "react")).toBeNull();
    expect(load("virtual:spaceworks-api-index")).toContain('"operationId":"loans_create"');
    const tags = load("virtual:spaceworks-api-tags");
    expect(tags).toContain('"loans": () => import("virtual:spaceworks-api-tag/loans")');
    expect(tags).toContain('export const version = "9.9.9"');
    expect(load("virtual:spaceworks-api-tag/stock")).toContain('"operationId":"stock_clear"');
    expect(() => load("virtual:spaceworks-api-tag/nope")).toThrow(/Unknown API reference tag/);
  });
});
