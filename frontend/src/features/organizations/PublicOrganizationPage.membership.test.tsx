import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api";
import legacy from "../publicPages/fixtures/review-r2.json";
import { PublicOrganizationPage } from "./PublicOrganizationPage";

const state = vi.hoisted(() => ({ directory: false, organization: {} as Record<string, unknown> }));
vi.mock("../publicPages/pageApi", async () => ({ ...await vi.importActual<typeof import("../publicPages/pageApi")>("../publicPages/pageApi"),
  usePublicPage: () => ({ error: new StructuredApiError(404, {}) }),
}));
vi.mock("./publicDirectoryApi", async () => ({ ...await vi.importActual<typeof import("./publicDirectoryApi")>("./publicDirectoryApi"),
  useOrganizationDirectoryEnabled: () => state.directory,
}));
vi.mock("../../lib/charges", () => ({ useChargesOn: () => true }));
vi.mock("./publicOrganizationsApi", () => ({
  usePublicOrganization: () => ({ data: state.organization }),
  usePublicOrganizationSpaces: () => ({ data: { count: 0, next: null, previous: null, results: [] } }),
  usePublicOrganizationEvents: () => ({ data: { count: 0, next: null, previous: null, results: [] } }),
}));

const HOME = { name: "Harbour Lab", slug: "harbour", logo_url: null, canonical_url: "/m/harbour" };
const PLAN = { id: 1, name: "Maker monthly", description: "", amount: "25.00", currency: "eur", joining_fee: "0.00",
  plan_type: "recurring", interval: "monthly", custom_days: null, fixed_end_date: null, join_mode: "open" };

function show(organization: Record<string, unknown>, directory = false) {
  state.organization = { ...legacy.legacy_organization, ...organization };
  state.directory = directory;
  return render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/o/builders"]}>
    <Routes><Route path="/o/:organizationSlug" element={<PublicOrganizationPage />} /></Routes>
  </MemoryRouter></QueryClientProvider>);
}

describe("organization page: plans and directory link (O-F5)", () => {
  it("links to the organization directory only while it is enabled", () => {
    const { unmount } = show({});
    expect(screen.queryByRole("link", { name: "Organizations" })).toBeNull();
    unmount();
    show({}, true);
    expect(screen.getAllByRole("link", { name: "Organizations" })[0]).toHaveAttribute("href", "/organizations");
  });

  it("hides the membership section while the home space's plans are off", () => {
    show({ plans: null, home_space: HOME });
    expect(screen.queryByRole("heading", { name: "Membership" })).toBeNull();
  });

  it("shows the home space's plans and who issues the member card", () => {
    show({ plans: { title: "", count: 1, results: [PLAN], collection_url: "" }, home_space: HOME });
    expect(screen.getByRole("heading", { name: "Membership" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Maker monthly" })).toBeInTheDocument();
    expect(screen.getByText(/Member cards are issued by Harbour Lab/)).toBeInTheDocument();
  });
});
