import { cleanup, render } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { EXEMPTIONS, exemption } from "./contracts.census-D12";
import { CONTEXTLESS } from "./contextless.census-D12";
import { PHASES } from "./fetch.census-D12";
import { exemptionProofFor } from "./exemptions.census-D12";
import { assertExemptPresentation, exemptPresentationFor } from "./refusals.census-D12";
import { routeInventory } from "./source.census-D12";

afterEach(cleanup);
it("every registered exemption resolves to a mount proof and an executable presentation witness", () => {
  const routes = routeInventory();
  for (const [key, phases] of Object.entries(EXEMPTIONS)) {
    const variants = routes.filter(row => key === row.screen || key === `${row.screen}:${row.pattern}`);
    expect(variants.length, `Unresolved exemption registration: ${key}`).toBeGreaterThan(0);
    for (const row of variants) for (const phase of PHASES.filter(phase => phases[phase])) {
      expect(exemption(row, phase)).toBeTruthy();
      expect(exemptionProofFor(row, phase).mounts.length).toBeGreaterThan(0);
      expect(exemptPresentationFor(row, phase)).toBeTypeOf("function");
    }
  }
  for (const contract of CONTEXTLESS) {
    const variants = routes.filter(row => row.screen === contract.screen && exemption(row, "error"));
    expect(variants.length, contract.screen).toBeGreaterThan(0);
    for (const row of variants) for (const phase of PHASES) {
      expect(exemptionProofFor(row, phase).mounts).toEqual([row.screen]);
      expect(exemptPresentationFor(row, phase)).toBeTypeOf("function");
    }
  }
});
it("rejects an exemption without a registered mount/presentation handler", async () => {
  const row = { ...routeInventory()[0], screen: "UnregisteredExemption" };
  await expect(assertExemptPresentation(row, "error", [])).rejects.toThrow("No mounted presentation proof");
});
it("rejects an empty main in place of the exempt not-found card", async () => {
  const row = routeInventory().find(row => row.screen === "NotFoundPage")!;
  render(<main />);
  await expect(assertExemptPresentation(row, "error", [])).rejects.toThrow("We couldn't find that page");
}, 10_000);

it("waits for the tenant alias's complete current home presentation", async () => {
  const row = routeInventory().find(row => row.screen === "SingleTenantHome")!;
  const view = render(<main><h1>D12 Lab</h1></main>);
  const proof = assertExemptPresentation(row, "empty", []);
  view.rerender(<main key="settled"><h1>D12 Lab</h1><a href="/inventory">Browse inventory</a><a href="/events">See events</a></main>);
  await expect(proof).resolves.toBeUndefined();
});
it("rejects a home title when the required destination links remain hidden", async () => {
  const row = routeInventory().find(row => row.screen === "SingleTenantHome")!;
  render(<main><h1>D12 Lab</h1><div hidden><a href="/inventory">Browse inventory</a><a href="/events">See events</a></div></main>);
  await expect(assertExemptPresentation(row, "empty", [])).rejects.toThrow("Browse inventory");
}, 10_000);
