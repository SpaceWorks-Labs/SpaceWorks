import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { moduleKeys, moduleLabel } from "../../lib/moduleLabels";
import { findDoc } from "../docs/docsIndex";
import { FeaturesPage } from "./FeaturesPage";
import { featureAreas } from "./featuresPage/featureAreas";
import { moduleDocs } from "./featuresPage/featureSummary";
import { moduleGroups, moduleSlug } from "./featuresPage/moduleGroups";

vi.mock("../hosting/hostingApi", () => ({ useHostingConfig: () => ({ data: false, isPending: false }) }));
vi.mock("../organizations/publicDirectoryApi", () => ({ useOrganizationDirectoryEnabled: () => false }));

function renderPage() {
  return render(<MemoryRouter initialEntries={["/features"]}><FeaturesPage /></MemoryRouter>);
}

describe("FeaturesPage", () => {
  it("shows every module once, as a card inside its group, linking to /features/<module>", () => {
    const { container } = renderPage();
    for (const group of moduleGroups()) {
      const section = document.getElementById(`group-${group.key}`)!;
      expect(within(section).getByRole("heading", { level: 2, name: group.title })).toBeInTheDocument();
      for (const key of group.modules) {
        const card = section.querySelector(`[data-module="${key}"]`)!;
        expect([key, card?.textContent?.includes(moduleLabel(key))]).toEqual([key, true]);
        expect(within(card as HTMLElement).getByRole("link", { name: moduleLabel(key) })).toHaveAttribute("href", `/features/${moduleSlug(key)}`);
      }
    }
    expect(container.querySelectorAll("[data-module]").length).toBe(moduleKeys().length);
  });

  it("puts counts on each card and a New in 0.12.0 strip that links to module pages", () => {
    renderPage();
    const card = document.querySelector('[data-module="events"]') as HTMLElement;
    expect(card.textContent).toMatch(/\d+ features · \d+ reports/);
    const strip = screen.getByRole("heading", { level: 2, name: "New in 0.12.0" }).closest("section")!;
    expect(within(strip).getByRole("link", { name: "Card Studio and certificates" })).toHaveAttribute("href", "/features/membership");
  });

  it("filters by search over names, features and reports, and says so when nothing matches", () => {
    renderPage();
    const box = screen.getByRole("searchbox", { name: "Search modules and features" });
    fireEvent.change(box, { target: { value: "heatmap" } });
    expect(document.querySelector('[data-module="machines"]')).not.toBeNull();
    expect(document.querySelector('[data-module="shop"]')).toBeNull();
    fireEvent.change(box, { target: { value: "zzzz-nothing" } });
    expect(screen.getByRole("status")).toHaveTextContent("No module matches");
    expect(document.querySelectorAll("[data-module]").length).toBe(0);
  });

  it("keeps the area data it was built on: each area has a published docs page", () => {
    for (const area of featureAreas()) expect([area.docs, findDoc(area.docs.slice("/docs/".length))]).not.toEqual([area.docs, undefined]);
    for (const key of moduleKeys()) expect(findDoc(moduleDocs(key).slice("/docs/".length))).toBeDefined();
  });

  it("marks Features current in the hub header, closes with Patch beside teal actions, and has no axe violations", async () => {
    const { container } = renderPage();
    const nav = screen.getAllByRole("navigation", { name: "Main" })[0];
    expect(within(nav).getByRole("link", { name: "Features" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("heading", { level: 1, name: "Everything Space Works does, module by module." })).toBeInTheDocument();
    const cta = screen.getByRole("heading", { level: 2, name: "Start with what you run today." }).closest("section")!;
    expect(cta.querySelector("[data-patch-moment]")).toHaveAttribute("aria-hidden", "true");
    expect(cta.querySelector(".sw-hub-cta-primary")).toBeNull(); // Patch is the bold moment: no orange beside it
    await expectNoA11yViolations(container);
  });
});

describe("FeaturesPage and the retired Printing module (decision 340b)", () => {
  it("shows no Printing card; Machine service is the one card for every machine type", () => {
    renderPage();
    expect(document.querySelector('[data-module="printing"]')).toBeNull();
    expect(screen.queryByRole("link", { name: "Printing" })).toBeNull();
    const machines = document.getElementById("group-machines")!;
    expect(machines.querySelector('[data-module="machine_service"]')).not.toBeNull();
    expect([...machines.querySelectorAll("[data-module]")].map(card => card.getAttribute("data-module"))).toEqual(["machines", "machine_service"]);
  });
});

vi.mock("./useLandingEnabled", () => ({ useLandingEnabled: () => ({ loading: false, enabled: true }) }));
vi.mock("./HubAccount", () => ({ HubAccount: () => <a href="/member">Sign in</a> }));
