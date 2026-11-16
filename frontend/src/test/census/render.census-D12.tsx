import { Component, type ErrorInfo, type ReactNode } from "react";
import { isDeepStrictEqual } from "node:util";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../../App";
import { TenantProvider } from "../../lib/tenant";
import { chooseTheme } from "../../lib/theme";
import { StructuredApiError } from "../../lib/api/errors";
import { clearAccessToken } from "../../lib/api/sessionTokens";
import { routeInventory, type RouteCase } from "./source.census-D12";
import { installFetch, PHASES, REFUSALS, type Phase } from "./fetch.census-D12";
import { emptyResponse } from "./schema.census-D12";
import { actionFor, activateAction } from "./actions.census-D12";
import { effectFor } from "./protocols.census-D12";
import { emptyCopyFor, stateCopyFor } from "./presentation.census-D12";
import { assertExemptPresentation, expectNoRetry } from "./refusals.census-D12";
import { EMPTY_COPY, FAILURE_COPY, MODULE_COPY, PERMISSION_COPY, productDefect, regressionId, exemption } from "./contracts.census-D12";
import { mountedScreens, observeQueryCaches } from "./observe.census-D12";
import { screenCopyFor, emptyFormFor, pendingCopyFor, autoRetryFor } from "./screenContracts.census-D12";
import { prepareScreen } from "./screenDrivers.census-D12";
import { exemptionProofFor } from "./exemptions.census-D12";
import { assertScreenRetries } from "./retries.census-D12";
import { warmLazyRoutes } from "./warm.census-D12";

const ROUTES = routeInventory();
// Pair the two themes with phone/desktop widths. No query, API helper, permission function,
// tenant hook, routed screen, or layout is mocked.
// Heavy staff panels (settings) need more than waitFor's 1 s default to commit copy in jsdom.
const PRESENT = 5000;
const DISPLAYS = [{ theme: "light", width: 1440 }, { theme: "dark", width: 390 }] as const;
const clients: QueryClient[] = [];
const disposers: (() => void)[] = [];
const crashes: string[] = [];
let observed: ReturnType<typeof observeQueryCaches>;
let currentPath = "";
function LocationProbe() { currentPath = useLocation().pathname; return null; }
class CrashProbe extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: Error, info: ErrorInfo) { crashes.push(`${error.message}\n${info.componentStack}`); }
  render() { return this.state.failed ? null : this.props.children; }
}
beforeEach(() => {
  observed = observeQueryCaches();
  crashes.length = 0;
  localStorage.clear(); sessionStorage.clear();
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  vi.stubGlobal("IntersectionObserver", class { observe() {} unobserve() {} disconnect() {} });
  vi.stubGlobal("scrollTo", vi.fn());
});
afterEach(async () => {
  cleanup();
  observed.restore();
  await Promise.all(clients.splice(0).map(async client => { await client.cancelQueries(); client.clear(); }));
  disposers.splice(0).forEach(dispose => dispose());
  observed.clear();
  await clearAccessToken("person"); await clearAccessToken("platform");
  delete window.__TENANT__;
  vi.unstubAllGlobals();
});
function visibleCopy(candidates: readonly string[]) {
  return candidates.flatMap(text => screen.queryAllByText(text, { exact: true }).filter(node => {
    // Testing Library's visibility matcher covers hidden/aria-hidden ancestors separately below.
    // A closed <dialog> (the member drawer) is not rendered either; its copy is not on screen.
    // An SVG <title> is an accessible name, never rendered copy.
    return node.tagName.toLowerCase() !== "title" && !node.closest('[hidden], [aria-hidden="true"], dialog:not([open])');
  }));
}
async function show(row: RouteCase, phase: Phase, display: typeof DISPLAYS[number]) {
  const platform = row.platform === true || row.screen === "SuperadminPage";
  if (row.screen.startsWith("StaffApp")) localStorage.setItem(`spaceworks.staff.selectedMakerspace:${platform ? "platform" : "person"}`, "1");
  const search = new URLSearchParams();
  if (platform) search.set("context", "platform");
  if (row.screen === "FirebaseBridgePage") search.set("space", "1");
  const action = actionFor(row);
  for (const [key, value] of Object.entries(action?.search ?? {})) search.set(key, value);
  // A staff-issued display link polls by a fragment-bound secret. Registration
  // is a separate provisioning flow, not the resource state of a paired link.
  const fragment = row.screen === "SpaceDisplayPage" ? "#k=d12-display-secret" : action?.fragment ?? effectFor(row)?.fragment ?? "";
  const path = `${row.path}${search.size ? `?${search}` : ""}${fragment}`;
  window.history.replaceState(null, "", path);
  window.__TENANT__ = { tenantToken: row.mode === "single" ? "d12-tenant" : "",
    uiDelightEnabled: false, uiEasterEggsEnabled: false };
  Object.defineProperty(window, "innerWidth", { value: display.width, configurable: true });
  vi.stubGlobal("matchMedia", (query: string) => ({ media: query,
    matches: query.includes("prefers-reduced-motion") || query.includes("max-width") && display.width === 390,
    onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => true }));
  chooseTheme(display.theme);
  const container = document.createElement("div");
  document.body.append(container);
  const proof = exemption(row, phase) ? exemptionProofFor(row, phase) : undefined;
  const targets = proof?.mounts ?? [row.screen.split("/")[0], ...(row.leaves ?? [])];
  const targetMounted = () => {
    if (!Object.keys(container).some(key => key.startsWith("__reactContainer$"))) return false;
    const mounted = new Set([...mountedScreens(container), ...observed.rendered]);
    return targets.every(target => mounted.has(target));
  };
  const networkRow = proof?.destination ? { ...row, screen: targets[0] } : row;
  const network = installFetch(phase, platform, networkRow, targetMounted, observed.requestOwner, observed.requestOperation, proof?.admissionOnly);
  disposers.push(network.dispose);
  const client = new QueryClient({ defaultOptions: { queries: {
    retry: false, retryDelay: 0, gcTime: Infinity, refetchOnWindowFocus: false,
  }, mutations: { retry: false } } });
  clients.push(client);
  const view = render(<QueryClientProvider client={client}><TenantProvider><MemoryRouter initialEntries={[path]}>
    <LocationProbe /><CrashProbe><App /></CrashProbe>
  </MemoryRouter></TenantProvider></QueryClientProvider>, { container });
  if (!exemption(row, phase)) { await prepareScreen(row); await activateAction(row, phase); }
  await waitFor(() => {
    expect(crashes, row.id).toEqual([]);
    expect(network.fixtureErrors, `Fixture contract: ${row.id}`).toEqual([]);
    const mounted = mountedScreens(view.container);
    for (const target of targets) expect([...mounted], `Admission did not mount ${target}: ${row.id}`).toContain(target);
    if (proof?.destination) expect(currentPath, `Redirect destination: ${row.id}`).toBe(proof.destination);
    if (!proof) {
      if (row.leaves) {
        expect(row.leaves, `Missing staff dispatch case: ${row.id}`).not.toEqual([]);
        for (const leaf of row.leaves) expect([...mounted], `Staff leaf not mounted: ${leaf}`).toContain(leaf);
      }
      // Decision 576: loading is a real full-page state too. MemberArea:183
      // withholds its entire shell while refresh/invalidation remains pending.
      if (row.memberTab && phase !== "loading") expect([...view.container.querySelectorAll('a[aria-current="page"]')]
        .map(link => link.getAttribute("href"))).toContain(row.path);
    }
    if (!proof && action && phase === "empty") expect(screen.getByText(action.idle, { exact: true })).toBeVisible();
    else if (!exemption(row, phase)) expect(network.own().length, `No domain fetch reached: ${row.id}`).not.toBe(0);
    else expect(view.container.querySelectorAll("main")).toHaveLength(1);
  // Cold lazy chunks under a loaded worker pool; stays below the 10 s hook timeout.
  }, { timeout: 8000 });
  expect(document.documentElement.classList.contains("dark")).toBe(display.theme === "dark");
  return { ...view, client, network };
}
async function assertSettled() {
  await waitFor(() => expect(observed.queries().filter(query => query.state.fetchStatus === "fetching")).toEqual([]));
  await waitFor(() => expect(observed.mutations().filter(mutation => mutation.state.status === "pending")).toEqual([]));
}
async function assertTypedErrors(phase: "error" | "permission" | "module") {
  await assertSettled();
  await waitFor(() => expect([...observed.errors, ...observed.queries().map(query => query.state.error),
    ...observed.mutations().map(mutation => mutation.state.error)].filter(Boolean).length).not.toBe(0));
  const errors = [...new Set([...observed.errors, ...observed.queries().map(query => query.state.error),
    ...observed.mutations().map(mutation => mutation.state.error)].filter(Boolean))];
  for (const error of errors) {
    expect(error).toBeInstanceOf(StructuredApiError);
    expect({ status: (error as StructuredApiError).status, code: (error as StructuredApiError).code })
      .toEqual({ status: REFUSALS[phase].status, code: REFUSALS[phase].code });
  }
}
export function registerRouteCensus(mode: "single" | "central") {
describe(`D12 every ${mode} production route, at the real fetch boundary`, () => {
  beforeAll(warmLazyRoutes, 300_000);
  for (const row of ROUTES.filter(row => row.mode === mode)) for (const display of DISPLAYS) for (const phase of PHASES) {
    const regression = regressionId(row, phase);
    describe(`${row.id} | ${display.theme}/${display.width} | ${phase}`, () => {
    let prepared: Awaited<ReturnType<typeof show>>;
    // Preserve the typed-error baseline for the repaired outage regression.
    beforeEach(async () => {
      prepared = await show(row, phase, display);
      // An exempt (e.g. contextless, request-free) variant has no exchange to pin.
      if (!exemption(row, phase) && (regression || productDefect(row, phase))) {
        if (phase === "error") await assertTypedErrors("error");
        else if (phase === "loading") expect(prepared.network.domain().map(exchange => exchange.status))
          .toEqual(prepared.network.domain().map(() => null));
        else if (phase === "empty") {
          await assertSettled();
          for (const exchange of prepared.network.domain()) expect({ status: exchange.status, body: exchange.body })
            .toEqual(emptyResponse(exchange.path, exchange.method));
          if (row.screen === "LegalPage") expect(prepared.network.domain().filter(exchange => exchange.path.startsWith("/discover/legal/"))
            .map(exchange => ({ status: exchange.status, body: exchange.body }))).toEqual([
              { status: 200, body: { slug: row.path.split("/").pop(), markdown: "", source: "platform", language: "", updated_at: null } },
            ]);
        }
      }
    });
    afterEach(() => { if (prepared) expect(prepared.network.fixtureErrors, row.id).toEqual([]); });
    const defect = productDefect(row, phase);
    it(defect ?? regression ?? "renders the declared state", async () => {
      const { network, container } = prepared;
      if (exemption(row, phase)) {
        expect(container.querySelectorAll("main")).toHaveLength(1);
        await assertExemptPresentation(row, phase, network.exchanges);
        expect(crashes).toEqual([]);
        return;
      }
      if (phase === "loading") {
        expect(network.domain().map(exchange => exchange.status)).toEqual(network.domain().map(() => null));
        const action = actionFor(row);
        if (action?.file) {
          expect(screen.getByLabelText(action.file.label)).toBeDisabled();
          expect(screen.getByText(`Uploading ${action.file.name}...`, { exact: true })).toHaveAttribute("role", "status");
        } else if (action) {
          // ActionControl's documented pending state is a named, disabled,
          // aria-busy button; a command need not show a whole-page LogoLoader.
          const pending = screen.getByRole("button", { busy: true });
          expect(pending).toBeVisible(); expect(pending).toBeDisabled();
          expect(pending).toHaveAccessibleName();
        } else {
          // Accept only named loaders or this screen's source-pinned pending
          // live-region sentence, never an unrelated ready-state status.
          // A redirecting panel (settings -> its landing section) commits its loader after one more render.
          const loaders = () => screen.queryAllByRole("status").filter(node => node.getAttribute("aria-label")
            || pendingCopyFor(row).includes(node.textContent?.trim() ?? ""));
          await waitFor(() => expect(loaders().length, `No labelled loader: ${row.id}`).not.toBe(0), { timeout: PRESENT });
          for (const loader of loaders()) expect(loader).toBeVisible();
        }
        expect(screen.queryByRole("alert")).toBeNull();
      } else if (phase === "empty") {
        await assertSettled();
        const action = actionFor(row);
        if (action) {
          expect(screen.getByText(action.idle, { exact: true })).toBeVisible();
          expect(network.domain().filter(exchange => exchange.method !== "GET")).toEqual([]);
          expect(crashes).toEqual([]);
          return;
        }
        for (const exchange of network.own()) {
          const expected = emptyResponse(exchange.path, exchange.method);
          expect({ status: exchange.status, body: exchange.body }).toEqual(expected);
          if (expected.status !== 404) {
            const data = [...observed.queries().map(query => query.state.data), ...observed.mutations().map(mutation => mutation.state.data), ...observed.localResults];
            // collectPublicPages returns rows, while paged queries retain the envelope.
            // Both exact cache shapes preserve the same empty collection contract.
            const page = exchange.body as { count?: number; next?: unknown; results?: unknown[] } | null;
            const collected = page?.count === 0 && page.next === null && Array.isArray(page.results) && page.results.length === 0;
            expect(data.some(value => isDeepStrictEqual(value, exchange.body)
              || collected && Array.isArray(value) && value.length === 0), `Unobserved response: ${exchange.path}`).toBe(true);
          }
        }
        for (const query of observed.queries().filter(query => query.state.error)) {
          expect(query.state.error).toBeInstanceOf(StructuredApiError);
          expect({ status: (query.state.error as StructuredApiError).status, code: (query.state.error as StructuredApiError).code })
            .toEqual({ status: 404, code: "not_found" });
        }
        const form = emptyFormFor(row);
        if (form && network.domain().every(exchange => exchange.status === 200)) {
          expect(screen.getByRole(form.role, { name: form.name })).toBeVisible();
          expect(crashes).toEqual([]); return;
        }
        const emptyCopy = [...EMPTY_COPY, ...emptyCopyFor(row), ...stateCopyFor(row, "empty"), ...screenCopyFor(row, "empty")];
        await waitFor(() => expect(visibleCopy(emptyCopy).length, `Missing explicit empty UI: ${row.id}`).not.toBe(0), { timeout: PRESENT });
        for (const message of visibleCopy(emptyCopy)) expect(message, `Hidden empty copy: ${message.textContent}`).toBeVisible();
        if (network.own().some(exchange => exchange.status === 404)) expectNoRetry(row, "not-found");
        expect(crashes).toEqual([]);
      } else {
        await assertTypedErrors(phase);
        const copy = [...(phase === "error" ? FAILURE_COPY : phase === "permission" ? PERMISSION_COPY : MODULE_COPY),
          ...stateCopyFor(row, phase), ...screenCopyFor(row, phase), `${REFUSALS[phase].detail} (${REFUSALS[phase].code})`];
        await waitFor(() => expect(visibleCopy(copy).length, `Missing ${phase} explanation: ${row.id}`).not.toBe(0), { timeout: PRESENT });
        for (const message of visibleCopy(copy)) expect(message).toBeVisible();
        if (phase !== "error") expectNoRetry(row, phase);
        if (phase === "error") {
          await assertScreenRetries(row, network, () => assertTypedErrors("error"), autoRetryFor(row)?.ms);
        }
      }
      expect(crashes).toEqual([]);
    // The first case of a heavy dashboard (many independent widgets) can exceed 15 s in a loaded pool.
    }, 30_000);
    });
  }
});
}
