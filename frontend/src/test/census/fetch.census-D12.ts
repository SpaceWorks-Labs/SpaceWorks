import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { vi } from "vitest";
import { ROOT } from "./source.census-D12";
import type { RouteCase } from "./source.census-D12";
import programmeFixture from "../../../../backend/tests/events/programme/contracts/fixtures/public-url-bootstrap-v3.json";
import type { ProgrammeContext } from "../../features/events/contracts/types";
import { admissionResponse, emptyResponse, operationFor } from "./schema.census-D12";
import { checkActionRequest } from "./actions.census-D12";

export type Phase = "loading" | "empty" | "error" | "permission" | "module";
export const PHASES: Phase[] = ["loading", "empty", "error", "permission", "module"];
export const REFUSALS = {
  error: { status: 503, code: "service_unavailable", detail: "Census service unavailable." },
  permission: { status: 403, code: "permission_denied", detail: "Census access denied." },
  module: { status: 404, code: "module_disabled", detail: "Census module is disabled.", module: "events" },
} as const;
const repo = resolve(ROOT, "..");
const definitions = resolve(repo, "backend/apps/makerspaces");
const files = readdirSync(definitions);
const definitionText = (prefix: string) => files.filter(file => file.startsWith(prefix) && file.endsWith(".py"))
  .map(file => readFileSync(resolve(definitions, file), "utf8")).join("\n");
const modules = [...definitionText("module_registry").matchAll(/ModuleDefinition\(\s*["']([\w]+)["']/g)].map(match => match[1]);
const capabilityText = definitionText("capability_definitions");
// Decision 319: registered retired keys always read off, even in a fully enabled world.
const retired = new Set([...(capabilityText.match(/RETIRED_FEATURES\s*=\s*frozenset\(\{([\s\S]*?)\}\)/)?.[1] ?? "")
  .matchAll(/["']([\w.]+)["']/g)].map(match => match[1]));
// Extension registries receive FeatureDefinition under a factory parameter
// (`feature`, `f`, ...). Match their first dotted key as well as direct calls.
const features = [...capabilityText.matchAll(/\b\w+\(\s*["']([\w]+\.[\w.]+)["']/g)]
  .map(match => match[1]).filter(key => !retired.has(key));
const actions = [...readFileSync(resolve(repo, "backend/apps/accounts/rbac_actions.py"), "utf8")
  .matchAll(/^\s+[A-Z_]+\s*=\s*"([a-z_]+)"/gm)].map(match => match[1]);
export const BOOTSTRAP = {
  makerspace: { id: 1, slug: "lab", name: "D12 Lab", public_code: "D12", location: "D12 Town", timezone: "UTC",
    geofence_enabled: false, membership_policy: "open", public_inventory_enabled: true, public_site_enabled: true,
    public_stats_enabled: true, logo_url: null, cover_image_url: null },
  modules: [...new Set(modules)], features: [...new Set(features)], workflows: [], edition: "makerspace",
  branding: { display_name: "D12 Lab" }, theme: {}, email_enabled: true,
  frontend: { type: "central", hostname: "localhost", allowed_origins: [] },
  public_api: { base_url: "/api/v1", publishable_key: "pk_d12", inventory_path: "/public/lab/inventory/" },
};
export const SPACE = { ...BOOTSTRAP.makerspace, enabled_modules: BOOTSTRAP.modules, enabled_features: BOOTSTRAP.features,
  branding_config: BOOTSTRAP.branding, theme_config: {}, hidden_from_central_directory: false,
  unavailable_apps: [], telegram_group_chat_id: "", frontend_domain: null };
export const USER = { id: 1, username: "d12-operator", display_name: "D12 Operator", email: "d12@example.test",
  kind: "person", role: "space_manager", is_superuser: false, is_platform: false, has_staff_role: true,
  has_elevated_authority: true, email_verified: true, must_change_password: false, mfa_enrolment_due: false,
  has_organizations: true, superadmin_actions: actions,
  booking_grants: [{ space_id: 1, makerspace_id: 1, makerspace_slug: "lab", name: "D12 Room", source: "booking_grant", permissions: actions }],
  event_grants: [{ event_id: 1, series_id: null, makerspace_id: 1, makerspace_slug: "lab", title: "D12 Event", source: "event_grant", permissions: actions }],
  staff_roles: [{ makerspace: SPACE, roles: [{ id: 1, slug: "space_manager", name: "Space Manager" }], actions }],
  makerspaces: [{ ...SPACE, role: "space_manager", role_id: 1, role_ids: [1], role_slug: "space_manager",
    role_slugs: ["space_manager"], role_name: "Space Manager", role_names: ["Space Manager"], actions,
    source: "membership", tracks: ["community", "staff"], can_configure_machine_types: true,
    is_machine_only: false, can_refer: true, can_verify: true, verified_at: null, referrals_enabled: true }] };
const TOKEN = `eyJhbGciOiJub25lIn0.${btoa(JSON.stringify({ user_id: 1, exp: 4102444800 }))}.d12`;
// `outside`: a request whose render-owner chain lies outside <App> (a provider render) while the target was
// mounted. It still receives the phase's answer, but it is never counted as the screen's own traffic.
export type Exchange = { path: string; method: string; support: boolean; status: number | null; body: unknown; outside?: boolean };
function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}
// These are admission fixtures only. Domain requests always pass through the real API and Query functions.
function support(path: string, platform: boolean, row?: RouteCase): unknown | undefined {
  // Reachability admits the online kiosk PIN screen; it is not a station unlock.
  if (path === "/health") return { status: "ok" };
  if (path === "/bootstrap") return BOOTSTRAP;
  if (path === "/auth/refresh") return { access: TOKEN, user: identity(platform) };
  if (path === "/auth/me") return identity(platform);
  if (path === "/admin/makerspaces") return [SPACE];
  if (path === "/recovery") return { mode: "normal" };
  // A healthy admission world has no paused/read-only-space warnings. Seeding
  // one warning per array fabricated an unrelated alert in every platform tab.
  if (path === "/platform-notices") return { announcements: [], spaces: [] };
  if (path === "/config" && row?.screen !== "HostingRequestPage") return { ...admissionResponse(path) as object, landing_enabled: true };
  if (/^\/public\/makerspaces\/lab\/availability$/.test(path)) return { state: "active" };
  if ((row?.memberTab || row?.screen.startsWith("MemberArea") || row?.screen === "MemberTabRoute") && path === "/memberships/me") return {
    memberships: [{ makerspace: SPACE, membership_status: "active", role: "member", waiver_acceptance_required: false,
      can_refer: true, can_verify: true, verified_at: null, referrals_enabled: true }], requests: [],
  };
  if (row?.file === "features/events/programme/EventProgrammePage.tsx"
      && /^\/public\/event-programmes\/[^/]+\/context$/.test(path)) {
    const ordinary = ["OrdinaryProgrammeRegistration", "DropInJourney"].includes(row.screen);
    const context = structuredClone(ordinary ? programmeFixture.ordinary_context : programmeFixture.context) as ProgrammeContext;
    // Context IDs and named URLs deliberately stay those of the canonical provider fixture.
    // This is server-owned event admission, independent of the ambient tenant selection.
    context.programme.capabilities["events.mentoring"] = true;
    context.programme.capabilities["events.volunteering"] = true;
    context.saved_details.readiness = "unavailable";
    context.routes.prefill = null;
    return context;
  }
  return undefined;
}
function identity(platform: boolean) {
  return platform ? { ...USER, role: "superadmin", is_superuser: true, kind: "platform", is_platform: true } : USER;
}
export function installFetch(phase: Phase, platform = false, row?: RouteCase, targetMounted = () => true,
  requestOwner: () => Set<string> | undefined = () => undefined) {
  const exchanges: Exchange[] = [];
  const fixtureErrors: string[] = [];
  let activePhase = phase;
  const pending = new Set<(response: Response) => void>();
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    try {
    const url = new URL(input instanceof Request ? input.url : String(input), "http://localhost");
    if (!url.pathname.startsWith("/api/")) throw new Error(`D12 unexpected non-API fetch ${url}`);
    const path = url.pathname.replace(/^\/api(?:\/v1)?/, "").replace(/\/$/, "") || "/";
    const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
    // live.ts: a 503 permanently disables SSE on deployments without the transport.
    // It is background admission traffic, never evidence for a screen's error state.
    if (path === "/live" && method === "GET") {
      const body = { code: "service_unavailable", detail: "Live transport is unavailable." };
      exchanges.push({ path, method, support: true, status: 503, body });
      return json(body, 503);
    }
    const fixture = support(path, platform, row);
    const exchange: Exchange = { path, method, support: fixture !== undefined, status: null, body: null };
    exchanges.push(exchange);
    if (fixture !== undefined) {
      exchange.status = 200; exchange.body = fixture;
      return json(fixture);
    }
    operationFor(path, method);
    // Only ancestors may receive successful seeded resources. Once the registered
    // screen/dispatch leaf mounts, its requests must exercise the requested state.
    // An owner chain outside <App> (a provider-level render while a cold lazy route
    // resolves) cannot tell ancestor from target; fall back to the committed tree,
    // and tag it so it never stands in for the screen's own request (own() below).
    const chain = requestOwner();
    const owner = chain?.has("App") ? chain : undefined;
    const owned = row && owner ? owner.has(row.screen.split("/")[0])
      && (!(row.leaves?.length) || row.leaves.some(leaf => owner.has(leaf))) : targetMounted();
    if (chain && !owner && owned) exchange.outside = true;
    if (method === "GET" && !owned) {
      exchange.support = true; exchange.status = 200;
      exchange.body = /^\/admin\/makerspaces\/1$/.test(path) ? SPACE : admissionResponse(path);
      return json(exchange.body);
    }
    if (method !== "GET") {
      const body = init?.body ?? (input instanceof Request ? await input.clone().text() : undefined);
      checkActionRequest(row, method, path, typeof body === "string" ? JSON.parse(body) : body,
        init?.headers ?? (input instanceof Request ? input.headers : undefined));
    }
    if (activePhase === "loading") return new Promise<Response>(resolveResponse => {
      pending.add(resolveResponse);
      (init?.signal ?? (input instanceof Request ? input.signal : undefined))?.addEventListener("abort", () => {
        pending.delete(resolveResponse);
        resolveResponse(json({ code: "cancelled", detail: "Census cancelled." }, 499));
      }, { once: true });
    });
    const result = activePhase === "empty" ? emptyResponse(path, method) : {
      status: REFUSALS[activePhase].status, body: REFUSALS[activePhase],
    };
    exchange.status = result.status; exchange.body = result.body;
    return json(result.body, result.status);
    } catch (error) {
      fixtureErrors.push(error instanceof Error ? error.message : String(error));
      throw error;
    }
  });
  vi.stubGlobal("fetch", mock);
  return { exchanges, mock, fixtureErrors, domain: () => exchanges.filter(exchange => !exchange.support),
    own: () => exchanges.filter(exchange => !exchange.support && !exchange.outside),
    setPhase(next: Phase) { activePhase = next; },
    dispose() { for (const finish of pending) finish(json({ code: "cancelled", detail: "Census cancelled." }, 499)); pending.clear(); } };
}
