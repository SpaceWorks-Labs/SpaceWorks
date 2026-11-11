import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import type { Makerspace } from "../../types/inventory";
import { HubLandingPage } from "./HubLandingPage";

const spaces: Makerspace[] = Array.from({ length: 7 }, (_, i) => ({ name: `Space ${i + 1}`, public_code: `C${i}`, slug: `space-${i + 1}`, location: "Town" }));
vi.mock("../inventory/usePublicInventory", () => ({
  usePublicMakerspaces: () => ({ data: spaces, isLoading: false, isError: false, isFetching: false, refetch: vi.fn() }),
}));
vi.mock("../hosting/hostingApi", () => ({ useHostingConfig: () => ({ data: false, isPending: false }) }));
const directory = vi.hoisted(() => ({ enabled: false }));
vi.mock("../organizations/publicDirectoryApi", () => ({ useOrganizationDirectoryEnabled: () => directory.enabled }));

function Where() { const location = useLocation(); return <p data-testid="where">{location.pathname}{location.search}</p>; }
function renderLanding() {
  return render(<MemoryRouter initialEntries={["/"]}><Routes>
    <Route path="/" element={<HubLandingPage />} /><Route path="/docs" element={<Where />} />
  </Routes></MemoryRouter>);
}

describe("HubLandingPage", () => {
  it("leads with the tagline as the only h1 and two ways in", () => {
    renderLanding();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1, name: "Run the space, not spreadsheets." })).toHaveClass("sw-hero-title");
    expect(screen.getByRole("link", { name: "Install Space Works" })).toHaveAttribute("href", "/docs/install-and-update");
    // The page's one Workshop Orange moment is the install button.
    expect(screen.getByRole("link", { name: "Install Space Works" })).toHaveClass("sw-hub-cta-primary");
    for (const fact of ["Open source under AGPL-3.0", "Self-hosted", "No licence fees"]) expect(screen.getByText(fact)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Find a space" })[0]).toHaveAttribute("href", "/spaces");
  });

  it("has Home, Spaces, Docs, GitHub, theme and Sign in in the header, with Home current", () => {
    renderLanding();
    const nav = screen.getAllByRole("navigation", { name: "Main" })[0];
    expect(within(nav).getByRole("link", { name: "Home" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Spaces" })).toHaveAttribute("href", "/spaces");
    expect(within(nav).getByRole("link", { name: "Docs" })).toHaveAttribute("href", "/docs");
    // Phones fold the nav into the menu, so the bar keeps its own Docs link beside Sign in.
    const barDocs = screen.getAllByRole("link", { name: "Docs" }).filter(link => !nav.contains(link));
    expect(barDocs).toHaveLength(1);
    expect(barDocs[0]).toHaveAttribute("href", "/docs");
    expect(within(nav).getByRole("link", { name: /GitHub/ })).toHaveAttribute("href", "https://github.com/SpaceWorks-Labs/SpaceWorks");
    expect(screen.getAllByRole("link", { name: "Sign in" })[0]).toHaveAttribute("href", "/member");
    expect(screen.getAllByRole("button", { name: /Switch to (dark|light) mode/ }).length).toBeGreaterThan(0);
  });

  it("walks the sample handover through the real states", () => {
    renderLanding();
    const story = screen.getByRole("region", { name: "Loan · Soldering station SS-03" });
    expect(within(story).getByText("Ready for pickup")).toBeInTheDocument();
    fireEvent.click(within(story).getByRole("button", { name: "Next step: Issued" }));
    expect(within(story).getByText("Box QR scanned and an issue photo taken")).toBeInTheDocument();
    fireEvent.click(within(story).getByRole("button", { name: "Next step: Returned" }));
    expect(within(story).getByText("Returned", { selector: "span" })).toBeInTheDocument();
    fireEvent.click(within(story).getByRole("button", { name: "Start again" }));
    expect(within(story).getByText("Waiting for review")).toBeInTheDocument();
  });

  it("switches areas as keyboard tabs", () => {
    renderLanding();
    const tabs = within(screen.getByRole("tablist", { name: "Areas" })).getAllByRole("tab");
    expect(tabs).toHaveLength(6);
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Box QR scan and photo before anything leaves");
    fireEvent.keyDown(tabs[0], { key: "ArrowDown" });
    expect(tabs[1]).toHaveAttribute("aria-selected", "true");
    expect(tabs[1]).toHaveFocus();
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Certifications before anyone runs a machine");
    fireEvent.keyDown(tabs[1], { key: "End" });
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Optional Stripe or Razorpay checkout");
  });

  it("marks the native apps as in development, with no store links", () => {
    renderLanding();
    const apps = screen.getByRole("heading", { level: 2, name: "On every phone today. Native apps next." }).closest("section")!;
    expect(within(apps).getAllByText("In development")).toHaveLength(2);
    expect(within(apps).getByText("Android app")).toBeInTheDocument();
    expect(within(apps).queryAllByRole("link")).toHaveLength(0);
  });

  it("shows the first spaces with a link to the directory, and searches the docs", () => {
    renderLanding();
    expect(screen.getByRole("heading", { level: 2, name: "Find a space near you" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /See all 7/ })).toHaveAttribute("href", "/spaces");
    expect(screen.getByRole("link", { name: /Architecture/ })).toHaveAttribute("href", "/docs/architecture/overview");
    fireEvent.change(screen.getByRole("searchbox", { name: "Search the documentation" }), { target: { value: "backup" } });
    fireEvent.click(screen.getByRole("button", { name: "Search docs" }));
    expect(screen.getByTestId("where")).toHaveTextContent("/docs?q=backup");
  });

  it("shows a captioned, control-free glimpse of the staff request queue in the app's own words", () => {
    renderLanding();
    const desk = screen.getByRole("figure", { name: /Sample data: the staff console’s request queue/ });
    for (const label of ["Pending approval", "Accepted", "Issued", "Partially returned", "Returned"]) {
      expect(within(desk).getByText(label)).toBeInTheDocument();
    }
    expect(within(desk).getByText("Issuing needs both the box scan and the photo.")).toBeInTheDocument();
    expect(within(desk).queryAllByRole("button")).toHaveLength(0);
    expect(within(desk).queryAllByRole("link")).toHaveLength(0);
  });

  it("explains the licence in plain words and links every project page", () => {
    renderLanding();
    const section = screen.getByRole("heading", { level: 2, name: "Open source, in plain words." }).closest("section")!;
    expect(within(section).getByText("AGPL-3.0-or-later")).toBeInTheDocument();
    expect(within(section).getByText("Running a changed version for others")).toBeInTheDocument();
    expect(within(section).getByText(/source of your changes, under the same licence/)).toBeInTheDocument();
    const links: [RegExp, string][] = [
      [/The licence, in plain words/, "/docs/project/license"],
      [/Third-party software and font licences/, "/docs/project/third-party"],
      [/Security policy/, "/docs/project/security-policy"],
      [/Contributing/, "/docs/project/contributing"],
      [/Changelog and release notes/, "/docs/changelog"],
      [/Source on GitHub/, "https://github.com/SpaceWorks-Labs/SpaceWorks"],
      [/LICENSE file/, "https://github.com/SpaceWorks-Labs/SpaceWorks/blob/main/LICENSE"],
    ];
    for (const [name, href] of links) expect(within(section).getByRole("link", { name })).toHaveAttribute("href", href);
  });

  it("opens the docs from six entry points, including the API reference", () => {
    renderLanding();
    const docs = screen.getByRole("heading", { level: 2, name: "Everything is written down." }).closest("section")!;
    const doors: [RegExp, string][] = [
      [/^Getting started/, "/docs/guide/getting-started"], [/^Tutorials/, "/docs/tutorials/overview"],
      [/^Hosting/, "/docs/hosting"], [/^Areas and modules/, "/docs/modules"],
      [/^API reference/, "/docs/api/reference"], [/^Architecture/, "/docs/architecture/overview"],
    ];
    for (const [name, href] of doors) expect(within(docs).getByRole("link", { name })).toHaveAttribute("href", href);
    expect(within(docs).getByRole("link", { name: "Browse all documentation" })).toHaveAttribute("href", "/docs");
  });

  it("carries docs, licence and project links in the footer with the build's version", () => {
    renderLanding();
    const footer = screen.getByRole("contentinfo");
    expect(within(footer).getByRole("navigation", { name: "Footer: Docs" })).toBeInTheDocument();
    expect(within(footer).getByRole("link", { name: "API reference" })).toHaveAttribute("href", "/docs/api/reference");
    expect(within(footer).getByRole("link", { name: "Licence" })).toHaveAttribute("href", "/docs/project/license");
    expect(within(footer).getByRole("link", { name: "Third-party and fonts" })).toHaveAttribute("href", "/docs/project/third-party");
    expect(within(footer).getByRole("link", { name: /LICENSE file/ })).toHaveAttribute("href", "https://github.com/SpaceWorks-Labs/SpaceWorks/blob/main/LICENSE");
    expect(within(footer).getByText(/Free software under AGPL-3\.0-or-later/)).toBeInTheDocument();
    expect(within(footer).getByRole("link", { name: `Version ${__SPACEWORKS_VERSION__}` })).toHaveAttribute("href", "/docs/changelog");
  });

  it("has the install command, the FAQ and no accessibility violations", async () => {
    const { container } = renderLanding();
    expect(screen.getByText(/releases\/latest\/download\/install\.sh \| sh/)).toBeInTheDocument();
    expect(screen.getByText("Is Space Works really free?").closest("details")).not.toBeNull();
    await expectNoA11yViolations(container);
  });

  it("links the organizations directory in the footer only when it is enabled", () => {
    directory.enabled = false;
    const { unmount } = renderLanding();
    expect(screen.queryByRole("link", { name: "Organizations" })).toBeNull();
    unmount();
    directory.enabled = true;
    renderLanding();
    expect(screen.getByRole("link", { name: "Organizations" })).toHaveAttribute("href", "/organizations");
    directory.enabled = false;
  });
});
