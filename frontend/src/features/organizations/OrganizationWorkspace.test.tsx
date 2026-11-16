import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api";
import { PublicOrganizationPage } from "./PublicOrganizationPage";

const workspace = {
  kind: "organization", space_noun: "organization", name: "Chess Society",
  events: [{ title: "Club night", starts_at: "2026-12-01T18:00:00Z", ends_at: "2026-12-01T21:00:00Z", timezone: "UTC", location: "Hall", public_token: "ev-1" }],
  rooms: [{ name: "Quiet room", kind: "meeting", description: "Six tables.", public_token: "room-1" }],
  plans: null,
};
const organization = { slug: "chess-society", name: "Chess Society", description: "Weekly chess.", website: "", logo_url: null,
  catalogue_links: {}, collections: null, canonical_url: "/o/chess-society",
  home_space: { name: "Chess Society", slug: "chess", logo_url: null, canonical_url: "/o/chess-society" },
  plans: { title: "Plans", count: 1, collection_url: "", results: [{ id: 1, name: "Annual", description: "", amount: "0.00", currency: "inr", interval: "yearly", plan_type: "recurring", join_mode: "open", joining_fee: "0.00" }] },
  workspace };
const state = vi.hoisted(() => ({ organization: null as unknown }));
vi.mock("../publicPages/pageApi", async () => ({ ...await vi.importActual<typeof import("../publicPages/pageApi")>("../publicPages/pageApi"),
  usePublicPage: () => ({ error: new StructuredApiError(404, {}) }) }));
vi.mock("./publicOrganizationsApi", () => ({
  usePublicOrganization: () => ({ data: state.organization }),
  usePublicOrganizationSpaces: () => ({ data: { count: 0, next: null, previous: null, results: [] } }),
  usePublicOrganizationEvents: () => ({ data: { count: 0, next: null, previous: null, results: [] } }),
}));
vi.mock("../../lib/charges", () => ({ useChargesOn: () => false }));

function show(data: unknown) {
  state.organization = data;
  return render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/o/chess-society"]}>
    <Routes><Route path="/o/:organizationSlug" element={<PublicOrganizationPage />} /></Routes></MemoryRouter></QueryClientProvider>);
}

it("renders the workspace's upcoming events and rooms on the organization page (decision 295)", () => {
  show(organization);
  const events = screen.getByRole("region", { name: "Upcoming events" });
  expect(within(events).getByRole("link", { name: "Club night" })).toHaveAttribute("href", "/m/chess/events/ev-1");
  const rooms = screen.getByRole("region", { name: "Rooms to book" });
  expect(within(rooms).getByText("Meeting room")).toBeInTheDocument();
  expect(within(rooms).getByRole("link", { name: "Book Quiet room" })).toHaveAttribute("href", "/m/chess/bookings/room-1");
  // The plans join here: no "join through" link back to the /m/ page that redirects to this one.
  const plans = screen.getByRole("region", { name: "Membership" });
  expect(within(plans).getByText("Choose a plan to join Chess Society.")).toBeInTheDocument();
  expect(within(plans).queryByText(/Members join through/)).not.toBeInTheDocument();
});

it("leaves out a section whose module is off and shows nothing for a makerspace home", () => {
  show({ ...organization, workspace: { ...workspace, events: null, rooms: [] } });
  expect(screen.queryByRole("region", { name: "Upcoming events" })).not.toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Rooms to book" })).not.toBeInTheDocument();
  show({ ...organization, workspace: null });
  expect(screen.getAllByText(/Members join through/).length).toBeGreaterThan(0);
});
