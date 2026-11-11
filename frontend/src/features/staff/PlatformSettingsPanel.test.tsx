import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { PlatformSettingsPanel } from "./PlatformSettingsPanel";

vi.mock("../../lib/api", async importOriginal => ({ ...(await importOriginal<typeof import("../../lib/api")>()), staffRequest: vi.fn(() => new Promise(() => {})) }));

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.pathname + location.search + location.hash}</p>;
}

function renderPanel(url: string, platformHosting = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[url]}>
    <Routes><Route path="/admin/platform" element={<PlatformSettingsPanel platformHosting={platformHosting} />} />
      <Route path="*" element={<Where />} /></Routes>
  </MemoryRouter></QueryClientProvider>);
}

describe("PlatformSettingsPanel", () => {
  it("keeps the deployment-wide configuration tabs", () => {
    renderPanel("/admin/platform");
    for (const name of ["Email", "Sign-in providers", "Single sign-on", "Messaging providers", "Mobile apps", "Chat templates", "Version & deployment"]) {
      expect(screen.getAllByText(name).length).toBeGreaterThan(0);
    }
    expect(screen.queryByText("Stripe Connect")).not.toBeInTheDocument();
    // Accounts, IP access, audit, drills and moves moved to their own platform pages.
    for (const name of ["Accounts", "IP access", "Restore drills", "Self-host moves"]) expect(screen.queryByText(name)).not.toBeInTheDocument();
  });

  it("shows Stripe Connect only on a hosted platform", () => {
    renderPanel("/admin/platform", true);
    expect(screen.getAllByText("Stripe Connect").length).toBeGreaterThan(0);
  });

  // Decision 255: the same groups as a space's settings, with a search over each page's help.
  it("groups the platform pages like a space's settings and keeps each ?section= link", () => {
    renderPanel("/admin/platform?section=email");
    const nav = within(screen.getByRole("navigation", { name: "Settings pages" }));
    expect(nav.getAllByRole("list").map(list => list.getAttribute("aria-label"))).toEqual(["People", "Areas", "Money", "Communication", "Integrations", "Administration"]);
    expect(nav.getByRole("link", { name: "Email" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("heading", { name: "Email" })).toBeInTheDocument();
    expect(nav.getByRole("link", { name: /Data & recovery.*opens its own page/ })).toHaveAttribute("href", expect.stringContaining("/admin/platform-data"));
  });

  it("filters the menu by title and help text", () => {
    renderPanel("/admin/platform");
    const nav = within(screen.getByRole("navigation", { name: "Settings pages" }));
    fireEvent.change(nav.getByRole("searchbox", { name: "Search settings" }), { target: { value: "whatsapp" } });
    expect(nav.getAllByRole("link").map(link => link.textContent)).toEqual(["Messaging providers"]);
    fireEvent.change(nav.getByRole("searchbox", { name: "Search settings" }), { target: { value: "zzzz" } });
    expect(nav.getByText("No settings match. Try another word.")).toBeInTheDocument();
  });

  it.each([
    ["accounts", "/admin/platform-access?section=accounts"],
    ["ip-access", "/admin/platform-security?section=ip-access"],
    ["audit", "/admin/platform-security?section=audit"],
    ["restore-drills", "/admin/platform-data?section=restore-drills"],
    ["selfhost-moves", "/admin/platform-data?section=selfhost-moves"],
    ["requests", "/admin/platform-spaces"],
  ])("sends an old ?section=%s link to its new page", (section, target) => {
    renderPanel(`/admin/platform?section=${section}`);
    expect(screen.getByTestId("where").textContent).toContain(target);
  });
});
