import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { organizationActionLabel } from "./lifecycleLabels";
import { OrganizationInvitations } from "./OrganizationInvitations";
import type { OrganizationDetail } from "./organizationsApi";

vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(),
  staffRequest: vi.fn(async () => ({ count: 0, next: null, previous: null, results: [] })) }));

const organization = { id: 4, slug: "guild", name: "Guild", governance_actions: ["manage_organization_members", "manage_organization_profile"],
  granted_actions: ["manage_events", "view_inventory", "some_future_action"] } as unknown as OrganizationDetail;

describe("OrganizationInvitations action labels (OR-5)", () => {
  it("words each governance and makerspace action instead of showing its code", async () => {
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <OrganizationInvitations organization={organization} /></QueryClientProvider>);
    expect(await screen.findByRole("checkbox", { name: "Manage organization members" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Edit the organization profile" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Manage events" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "View inventory" })).toBeInTheDocument();
    expect(screen.queryByText(/manage_|view_inventory/)).toBeNull();
  });

  it("falls back to readable words for an action added later", () => {
    expect(organizationActionLabel("some_future_action")).not.toContain("_");
  });
});
