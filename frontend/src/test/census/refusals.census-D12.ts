import { screen, waitFor } from "@testing-library/react";
import { expect } from "vitest";
import type { RouteCase } from "./source.census-D12";
import { REFUSALS, type Exchange, type Phase } from "./fetch.census-D12";
import { emptyResponse } from "./schema.census-D12";
import { retryCopyFor } from "./presentation.census-D12";
import { contextlessNotice } from "./contextless.census-D12";
import { exemptionProofFor } from "./exemptions.census-D12";

const PRESENT = 5000;

/** Every name a retry control may carry: the shared labels plus the screen's own source-pinned retry copy. */
export function retryControls(row: RouteCase) {
  const names = [...new Set(["Retry", "Try again", "Check again", "Reload", ...retryCopyFor(row)])];
  return screen.queryAllByRole("button", { name: name => names.includes(name) });
}

/** Decision 588: Retry only where a retry can succeed (5xx, 429 or no response). A refusal - 403, the typed
 *  module 404 or a plain 404 - answers the same way again, so the screen must not offer Retry for it. */
export function expectNoRetry(row: RouteCase, phase: string, checkInstructions = true) {
  // Name each offending control with the text around it, so a red case says which widget offered it.
  const offered = retryControls(row).map(control => `${control.textContent} @ ${(control.parentElement?.textContent ?? "").slice(0, 160)}`);
  expect(offered.join(" || "), `Retry offered on a ${phase} refusal: ${row.id}`).toBe("");
  if (!checkInstructions) return;
  const instructions = screen.queryAllByText(/try again|retry later|check your (?:internet |network )?connection|temporarily unavailable/i)
    .filter(node => node.tagName.toLowerCase() !== "title" && !node.closest('[hidden], [aria-hidden="true"], dialog:not([open])'));
  expect(instructions.map(node => node.textContent), `Outage instructions on a ${phase} refusal: ${row.id}`).toEqual([]);
}

function answered(exchanges: Exchange[], path: string, phase: Phase) {
  const sent = exchanges.filter(exchange => exchange.path === path && exchange.method === "GET");
  expect(sent.length, `${path} was never sent`).not.toBe(0);
  const expected = phase === "empty" ? { ...emptyResponse(path, "GET"), support: false }
    : phase === "loading" ? { status: null, body: null, support: false }
    : { status: REFUSALS[phase].status, body: REFUSALS[phase], support: false };
  for (const exchange of sent) expect({ status: exchange.status, body: exchange.body, support: exchange.support }).toEqual(expected);
}

/**
 * An exemption removes a generic state assertion; it never removes the presentation its decision selects.
 * Each exempt variant asserts that decided presentation, not only that the page has one <main>.
 */
type Presentation = (row: RouteCase, phase: Phase, exchanges: Exchange[]) => Promise<void>;
async function heading(name: string) {
  await waitFor(() => expect(screen.getByRole("heading", { level: 1, name })).toBeVisible(), { timeout: PRESENT });
}
async function link(name: string, href: string) {
  await waitFor(() => {
    const matches = screen.getAllByRole("link", { name }).filter(node => node.getAttribute("href") === href);
    expect(matches.length, name + " -> " + href).toBeGreaterThan(0);
    for (const node of matches) expect(node).toBeVisible();
  }, { timeout: PRESENT });
}
async function home() {
  await waitFor(() => {
    expect(screen.getByRole("heading", { level: 1, name: "D12 Lab" })).toBeVisible();
    for (const label of ["Browse inventory", "See events"]) expect(screen.getAllByRole("link", { name: label })[0]).toBeVisible();
  }, { timeout: PRESENT });
}
const presentations: Record<string, Presentation> = {
  contextless: async (row, phase) => {
    const notice = contextlessNotice(row, phase);
    expect(notice, `Missing contextless witness: ${row.id}`).toBeTruthy();
    // A central route with no selected space says so instead of a false "no orders yet" or a blank detail.
    expect(await screen.findByText(notice!, { exact: true }, { timeout: PRESENT })).toBeVisible();
    expectNoRetry(row, `contextless ${phase}`);
  },
  AboutLandingGate: async () => { await heading("Run the space, not spreadsheets."); },
  LandingGate: async (_row, phase, exchanges) => {
    // Decisions 300/424: an empty, failed or refused directory read selects the bundled landing article.
    await heading("Run the space, not spreadsheets.");
    answered(exchanges, "/public/makerspaces", phase);
  },
  SpaceDisplayPage: async (_row, _phase, exchanges) => {
    // An AllowAny wall display has no permission state: a 403 reads as a transient outage it keeps polling through.
    const status = await screen.findByText("Can't reach the server. Trying again…", { exact: true }, { timeout: PRESENT });
    expect(status).toBeVisible(); expect(status).toHaveAttribute("role", "status");
    const sent = exchanges.filter(exchange => !exchange.support && !exchange.outside);
    expect(sent.length).toBeGreaterThan(0);
    for (const exchange of sent) expect({ status: exchange.status, code: (exchange.body as { code: string }).code })
      .toEqual({ status: 403, code: "permission_denied" });
  },
  FamilyHome: async () => {
    // The overview is its hero and shortcuts; sections with nothing to show are absent, never empty headings.
    // One settled snapshot: the overview may re-render (published page, closures) before it settles.
    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1, name: "D12 Lab" })).toBeVisible();
      for (const label of ["Browse inventory", "See events"]) expect(screen.getAllByRole("link", { name: label })[0]).toBeVisible();
      for (const section of ["Featured activities", "Book a space"]) expect(screen.queryByRole("heading", { name: section })).toBeNull();
    }, { timeout: PRESENT });
  },
  NotFoundPage: async (row) => {
    await heading("We couldn't find that page");
    expect(await screen.findByText("The link may be old, or the page moved.", { exact: true })).toBeVisible();
    await link("Back to home", row.path.startsWith("/m/") ? "/m/lab" : "/");
  },
  FeaturesPage: async () => {
    await heading("Everything Space Works does, module by module.");
    await link("Find a live space", "/spaces");
  },
  FeatureModulePage: async () => { await heading("Events"); await link("All modules", "/features"); },
  HelpPage: async row => {
    const base = row.pattern.includes(":slug") ? "/m/lab/help" : "/help";
    if (row.pattern.includes(":articleSlug")) {
      await heading("We couldn't find that article"); await link("Browse the guide", base);
    } else {
      await heading(row.pattern.includes(":sectionId") ? "Members and visitors" : "How can we help?");
      expect(await screen.findByRole("searchbox", { name: "Search the guide" }, { timeout: PRESENT })).toBeVisible();
    }
  },
  DocsPage: async () => { await heading("Space Works documentation"); await link("API reference", "/docs/api/reference"); },
  GithubAppCallbackPage: async () => {
    await heading("Open in the Space Works app");
    expect(await screen.findByRole("button", { name: "Open the app" })).toBeVisible();
    await link("Sign in on the website", "/member");
  },
  "tenant-home": home,
  "print-alias": async () => {
    await heading("Request a job");
    expect(await screen.findByRole("button", { name: "Cancel" })).toBeVisible();
  },
  "superadmin-alias": async () => {
    await heading("Choose a makerspace to operate");
    await link("Open the platform console", "/admin/platform-dashboard?context=platform");
  },
  "programme-index": async (_row, _phase, exchanges) => {
    // The destination may reuse the parent's admitted application while its own read is pending.
    // Select an exact destination sentence from the actual application response, never a parent loader.
    await waitFor(() => {
      const reads = exchanges.filter(exchange => exchange.method === "GET" && exchange.path.endsWith("/application"));
      expect(reads.length, "Programme destination has no application read").toBeGreaterThan(0);
      const last = reads[reads.length - 1];
      const data = [...reads].reverse().find(exchange => exchange.status === 200)?.body as { state?: string } | undefined;
      const failed = last.status !== null && last.status !== 200;
      const title = failed || !data ? "Event application" : data.state === "draft" ? "Apply to make something together" : "Your application";
      expect(screen.getByRole("heading", { level: 1, name: title })).toBeVisible();
    }, { timeout: PRESENT });
  },
  "programme-missing": async () => {
    const status = await screen.findByText("This part of the programme is unavailable. Choose an available step above.", { exact: true }, { timeout: PRESENT });
    expect(status).toBeVisible(); expect(status).toHaveAttribute("role", "status");
    expect(await screen.findByRole("link", { name: "Tickets and certificates" })).toBeVisible();
  },
  "reauth-callback": async () => {
    await heading("Identity provider returned");
    expect(await screen.findByText("Return to the browser window that opened this page.", { exact: true })).toBeVisible();
    expect(await screen.findByRole("button", { name: "Close this window" })).toBeVisible();
  },
  "reauth-confirm": async () => {
    await heading("Confirm authenticator enrollment");
    expect(await screen.findByText("This link works once, in the same browser session that requested it.", { exact: true })).toBeVisible();
    expect(await screen.findByRole("button", { name: "Confirm enrollment" })).toBeVisible();
  },
};
export function exemptPresentationFor(row: RouteCase, phase: Phase) {
  const proof = exemptionProofFor(row, phase);
  const presentation = presentations[proof.kind];
  if (!presentation) throw new Error(`No visible presentation witness for ${row.id} / ${phase} (${proof.kind})`);
  return presentation;
}
export async function assertExemptPresentation(row: RouteCase, phase: Phase, exchanges: Exchange[]) {
  await exemptPresentationFor(row, phase)(row, phase, exchanges);
  // The request-free native handoff describes reopening the app, not a refused API read.
  if (phase === "permission" || phase === "module") expectNoRetry(row, phase, row.screen !== "GithubAppCallbackPage");
}
