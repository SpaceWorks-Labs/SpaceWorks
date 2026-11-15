import { screen, waitFor } from "@testing-library/react";
import { expect } from "vitest";
import type { RouteCase } from "./source.census-D12";
import { REFUSALS, type Exchange, type Phase } from "./fetch.census-D12";
import { emptyResponse } from "./schema.census-D12";
import { retryCopyFor } from "./presentation.census-D12";
import { contextlessNotice } from "./contextless.census-D12";

const PRESENT = 5000;

/** Every name a retry control may carry: the shared labels plus the screen's own source-pinned retry copy. */
export function retryControls(row: RouteCase) {
  const names = [...new Set(["Retry", "Try again", "Check again", "Reload", ...retryCopyFor(row)])];
  return names.flatMap(name => screen.queryAllByRole("button", { name }));
}

/** Decision 588: Retry only where a retry can succeed (5xx, 429 or no response). A refusal - 403, the typed
 *  module 404 or a plain 404 - answers the same way again, so the screen must not offer Retry for it. */
export function expectNoRetry(row: RouteCase, phase: string) {
  // Name each offending control with the text around it, so a red case says which widget offered it.
  const offered = retryControls(row).map(control => `${control.textContent} @ ${(control.parentElement?.textContent ?? "").slice(0, 160)}`);
  expect(offered.join(" || "), `Retry offered on a ${phase} refusal: ${row.id}`).toBe("");
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
export async function assertExemptPresentation(row: RouteCase, phase: Phase, exchanges: Exchange[]) {
  if (phase === "permission" || phase === "module") expectNoRetry(row, phase);
  const notice = contextlessNotice(row, phase);
  if (notice) {
    // A central route with no selected space says so instead of a false "no orders yet" or a blank detail.
    expect(await screen.findByText(notice, { exact: true }, { timeout: PRESENT })).toBeVisible();
    expectNoRetry(row, `contextless ${phase}`);
  }
  if (row.screen === "LandingGate") {
    // Decisions 300/424: an empty, failed or refused directory read selects the bundled landing article.
    expect(await screen.findByRole("heading", { level: 1, name: "Run the space, not spreadsheets." }, { timeout: PRESENT })).toBeVisible();
    answered(exchanges, "/public/makerspaces", phase);
  }
  if (row.screen === "SpaceDisplayPage" && phase === "permission") {
    // An AllowAny wall display has no permission state: a 403 reads as a transient outage it keeps polling through.
    const status = await screen.findByText("Can't reach the server. Trying again…", { exact: true }, { timeout: PRESENT });
    expect(status).toBeVisible(); expect(status).toHaveAttribute("role", "status");
    expect(exchanges.filter(exchange => !exchange.support).map(exchange => exchange.status)).toContain(REFUSALS.permission.status);
  }
  if (row.screen === "FamilyHome") {
    // The overview is its hero and shortcuts; sections with nothing to show are absent, never empty headings.
    // One settled snapshot: the overview may re-render (published page, closures) before it settles.
    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1, name: "D12 Lab" })).toBeVisible();
      for (const label of ["Browse inventory", "See events"]) expect(screen.getAllByRole("link", { name: label })[0]).toBeVisible();
      for (const section of ["Featured activities", "Book a space"]) expect(screen.queryByRole("heading", { name: section })).toBeNull();
    }, { timeout: PRESENT });
  }
}
