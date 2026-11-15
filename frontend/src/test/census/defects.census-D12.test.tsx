import { afterEach, expect, it, vi } from "vitest";
import { i18n } from "../../lib/i18n";
import { checkedLine } from "../../features/cards/CardVerifyPage";
import { fetchJson } from "../../lib/api/requests";
import { StructuredApiError } from "../../lib/api/errors";
import { startKioskSession } from "../../features/kiosk/kioskApi";
import { displayScreenApi } from "../../features/spaceDisplay/api";
import ts from "typescript";
import { resolve } from "node:path";
import { ROOT, source } from "./source.census-D12";
import { operationFor } from "./schema.census-D12";

afterEach(() => vi.unstubAllGlobals());

// Backend implementations paginate these reads; the response annotations still
// advertise arrays. Fix each annotation to a page schema and regenerate OpenAPI.
for (const [path, location] of [
  ["/public/makerspaces", "backend/apps/inventory/views.py:47"],
  ["/public/lab/inventory/categories", "backend/apps/inventory/views.py:165"],
  ["/public/lab/spaces", "backend/apps/bookings/views_public.py:47"],
  ["/admin/makerspaces/1/member-cards", "backend/apps/makerspaces/member_card_admin_views.py:74"],
] as const) it.fails(`CENSUS-D12-57: ${location} documents the actual page for ${path}`, () => {
  const response = operationFor(path).operation.responses?.["200"]?.content?.["application/json"]?.schema;
  const spec = JSON.parse(ts.sys.readFile(resolve(ROOT, "openapi-schema.json"))!);
  const schema = response?.$ref ? spec.components.schemas[response.$ref.split("/").pop()!] : response;
  expect(schema?.type).toBe("object");
  expect(Object.keys(schema?.properties ?? {}).sort()).toEqual(["count", "next", "previous", "results"]);
});

// fetchJson drops the response JSON entirely. The public inventory/discovery
// queries therefore cannot distinguish 404/module_disabled from 404/not_found.
it.each([
  { status: 503, code: "service_unavailable" },
  { status: 403, code: "permission_denied" },
  { status: 404, code: "module_disabled" },
])("CENSUS-D12-35: fetchJson preserves $status/$code", async ({ status, code }) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ code, detail: "Census refusal." }),
    { status, headers: { "Content-Type": "application/json" } })));
  const result = await fetchJson("/api/v1/public/makerspaces/").catch(error => error);
  expect(result).toBeInstanceOf(StructuredApiError);
  const error = result as StructuredApiError;
  expect({ status: error.status, code: error.code }).toEqual({ status, code });
});

for (const [id, file, suffix] of [
  ["CENSUS-D12-51", "AttendanceReplyPage", "attendance"],
  ["CENSUS-D12-52", "CrewSignupPage", "crew-signup"],
] as const) {
  it(`${id}: the canonical member GET is documented`, () => {
    expect(operationFor(`/member/events/1/${suffix}`).pattern).toBe(`/api/v1/member/events/{id}/${suffix}/`);
  });
  it(`${id}: programme links use the member API namespace`, () => {
    let path: string | undefined;
    const walk = (node: ts.Node) => {
      if (ts.isVariableDeclaration(node) && node.name.getText() === "url") path = node.initializer?.getText();
      ts.forEachChild(node, walk);
    };
    walk(source(resolve(ROOT, `src/features/events/participation/${file}.tsx`)));
    expect(path).toBe('`/member/events/${Number(eventId)}/' + suffix + '/`');
  });
}

it("CENSUS-D12-2: card verification timestamps are a Lingui-marked sentence", () => {
  const translate = vi.spyOn(i18n, "_");
  try {
    checkedLine({ checked_at: "2026-11-15T12:00:00Z", timezone: "UTC" });
    expect(translate).toHaveBeenCalledTimes(1);
  } finally { translate.mockRestore(); }
});

// kioskApi.ts:62 discards the refusal JSON; api.ts:62 drops it in DisplayHttpError.
// Keep these transport pins separate from any missing browser action/parent fixture.
for (const [id, request] of [
  ["CENSUS-D12-36", () => startKioskSession("d12-station", "12345678", "lab")],
  ["CENSUS-D12-37", () => displayScreenApi.state("d12-display-secret")],
] as const) it.each([
  { status: 503, code: "service_unavailable" },
  { status: 403, code: "permission_denied" },
  { status: 404, code: "module_disabled" },
])(`${id}: preserves $status/$code`, async ({ status, code }) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ code, detail: "Census refusal." }),
    { status, headers: { "Content-Type": "application/json" } })));
  const error = await request().catch(error => error);
  expect(error).toBeInstanceOf(StructuredApiError);
  expect({ status: (error as StructuredApiError).status, code: (error as StructuredApiError).code }).toEqual({ status, code });
});
