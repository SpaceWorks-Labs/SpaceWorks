import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../../test/axe";
import { FEATURE_DEFINITIONS } from "../../../lib/features";
import { moduleKeys, moduleLabel } from "../../../lib/moduleLabels";
import { FeatureModulePage } from "./FeatureModulePage";
import { featureCatalogue } from "./catalogue";
import { featuresByModule, isProductFeature } from "./moduleFeatures";
import { moduleSlug } from "./moduleGroups";

vi.mock("../../hosting/hostingApi", () => ({ useHostingConfig: () => ({ data: false, isPending: false }) }));
vi.mock("../../organizations/publicDirectoryApi", () => ({ useOrganizationDirectoryEnabled: () => false }));

function renderAt(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/features/:module" element={<FeatureModulePage />} /></Routes></MemoryRouter>);
}

describe("FeatureModulePage", () => {
  it("renders features, reports, analytics, limits and integrations for a module from the catalogue", () => {
    renderAt("/features/machines");
    expect(screen.getByRole("heading", { level: 1, name: "Machines" })).toBeInTheDocument();
    const entry = featureCatalogue().machines;
    const panel = (kind: string) => document.querySelector(`[data-panel="${kind}"]`) as HTMLElement;
    for (const report of entry.reports) expect(within(panel("reports")).getByText(report.title)).toBeInTheDocument();
    for (const limit of entry.limits) expect(within(panel("limits")).getByText(limit)).toBeInTheDocument();
    for (const item of entry.integrations) expect(within(panel("integrations")).getByText(item)).toBeInTheDocument();
    for (const item of entry.analytics) expect(within(panel("analytics")).getByText(item)).toBeInTheDocument();
    for (const feature of featuresByModule().machines) expect(panel("features").querySelector(`[data-feature="${feature.key}"]`)).toHaveTextContent(feature.label);
    expect(screen.getByRole("link", { name: "Read the Machines docs" })).toHaveAttribute("href", "/docs/modules/machines");
    expect(screen.getByRole("link", { name: /All modules/ })).toHaveAttribute("href", "/features");
  });

  it("says why a module has no limit of its own, and lists new 0.12.0 items where there are some", () => {
    renderAt("/features/containers");
    expect(screen.getByText(/counted by the boxes limit/)).toBeInTheDocument();
    expect(document.querySelector('[data-panel="new"]')).toBeNull();
    renderAt("/features/membership");
    expect(screen.getAllByText("Card Studio with certificates").length).toBeGreaterThan(0);
  });

  it("shows the mascot, never invented UI, while a module has no screenshot", () => {
    renderAt("/features/shop");
    expect(document.querySelector("[data-shots='0'] [data-patch-moment]")).not.toBeNull();
    expect(document.querySelector("img")).toBeNull();
  });

  it("answers an unknown module with the app's 404", () => {
    renderAt("/features/not-a-module");
    expect(screen.getByText("404")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 1, name: /Machines/ })).toBeNull();
  });

  it("renders every module on one template without axe violations", async () => {
    for (const key of moduleKeys()) {
      const { unmount } = renderAt(`/features/${moduleSlug(key)}`);
      expect([key, screen.getByRole("heading", { level: 1 }).textContent]).toEqual([key, moduleLabel(key)]);
      unmount();
    }
    const { container } = renderAt("/features/events");
    await expectNoA11yViolations(container);
  });

  it("lists every product feature definition on exactly one module page", () => {
    const listed = Object.values(featuresByModule()).flat().map(feature => feature.key);
    expect(new Set(listed).size).toBe(listed.length);
    expect([...listed].sort()).toEqual(FEATURE_DEFINITIONS.filter(isProductFeature).map(feature => feature.key).sort());
  });
});

describe("FeatureModulePage and the retired Printing module (decision 340b)", () => {
  it("redirects /features/printing to the Machine service page, which describes the 3D print queue", () => {
    renderAt("/features/printing");
    expect(screen.getByRole("heading", { level: 1, name: "Machine service" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 1, name: "Printing" })).toBeNull();
    expect(screen.queryByText("404")).toBeNull();
    expect(screen.getAllByText(/3D print queue is one machine type here/).length).toBeGreaterThan(0);
  });
});
