import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OrganizationsPanel } from "./OrganizationsPanel";

const { useOrganizations, useOrganization } = vi.hoisted(() => ({ useOrganizations: vi.fn(), useOrganization: vi.fn() }));
vi.mock("../organizationsApi", () => ({ useOrganizations, useOrganization }));
vi.mock("../OrganizationProfileForm", () => ({ OrganizationProfileForm: () => <p>Profile fields</p> }));
vi.mock("../OrganizationMemberships", () => ({ OrganizationMemberships: () => <p>Organization people</p> }));
vi.mock("../OrganizationInvitations", () => ({ OrganizationInvitations: () => <p>Invitation controls</p> }));
// Self-creation (org-setup) reads the tenant origin; this suite covers the governance index, not that entry point.
vi.mock("../../../lib/tenant", () => ({ useTenant: () => ({ mode: "central" }) }));
vi.mock("../../organizations/OrganizationSelfCreation", () => ({ useOrganizationSelfCreationVisible: () => false, OrganizationSelfCreation: () => null }));
vi.mock("../OrganizationSetup", () => ({ OrganizationCreate: () => <p>Create organization form</p>, OrganizationLinks: () => <p>Linked spaces</p> }));

describe("organizations workspace", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/admin/organizations");
    useOrganizations.mockReturnValue({ isLoading: false, isError: false, data: { count: 2, results: [{ id: 1, name: "North", slug: "north" }, { id: 2, name: "South", slug: "south" }] } });
    useOrganization.mockImplementation((id: number | null) => ({ isLoading: false, isError: false, data: id ? { id, name: "North", slug: "north", governance_actions: [], public_profile_enabled: true } : undefined }));
  });
  it("opens an organization from the card index and keeps a shareable selection", () => {
    render(<QueryClientProvider client={new QueryClient()}><OrganizationsPanel /></QueryClientProvider>);
    fireEvent.click(screen.getByRole("button", { name: /North/ }));
    expect(screen.getByRole("heading", { level: 1, name: "North" })).toBeVisible();
    expect(screen.getByText("Profile fields")).toBeVisible();
    expect(new URLSearchParams(window.location.search).get("org")).toBe("1");
    expect(screen.getByRole("link", { name: "View public page ↗" })).toHaveAttribute("href", "/o/north");
  });
  it("opens the only organization directly", async () => {
    useOrganizations.mockReturnValue({ isLoading: false, isError: false, data: { count: 1, results: [{ id: 1, name: "North", slug: "north" }] } });
    render(<QueryClientProvider client={new QueryClient()}><OrganizationsPanel /></QueryClientProvider>);
    expect(await screen.findByText("Profile fields")).toBeVisible();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });
});
