import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api";
import legacy from "../publicPages/fixtures/review-r2.json";
import type { PublicOrganizationEvent, OrganizationArchiveEvent } from "../../generated/api";
import { PublicOrganizationPage } from "./PublicOrganizationPage";

const upcomingEvent = (title: string, token: string, host: PublicOrganizationEvent["host"], amount: string): PublicOrganizationEvent => ({
  public_token: token, title, description: "", starts_at: "2026-11-01T10:00:00Z", ends_at: "2026-11-01T12:00:00Z", location: "", location_kind: "indoor", capacity: 20,
  website: null, image_url: null, accent_preset: "maker_teal", availability: "Available", payment_amount: amount, currency: "eur", host, status: "published", event_url: `https://space.example/e/${token}`,
  delivery_mode: null, indexable: true, participating_organizations: [], audience_label: null, registration_audience: "accounts", category: null, tags: [], ticket_types: [], ticket_selection_required: false, promo_codes_enabled: false,
  custom_form: null, show_registration_count: false, registration_count: null, registration_requires_approval: false, effective_registration_cutoff_at: null, registration_open: true, organizers: [], series: null, timezone_name: "UTC", submission_stages: [],
});
const archived: OrganizationArchiveEvent = { kind: "archive", timezone: "UTC", title: "Archive workshop", description: "Past excerpt", starts_at: "2020-01-01T10:00:00Z", ends_at: "2020-01-01T12:00:00Z", event_url: null, host: { name: "Other venue", canonical_url: "https://space.example/other" } };
const { eventCalls, spaceCalls } = vi.hoisted(() => ({ eventCalls: vi.fn(), spaceCalls: vi.fn() }));
vi.mock("../publicPages/pageApi", async () => ({ ...await vi.importActual<typeof import("../publicPages/pageApi")>("../publicPages/pageApi"),
  usePublicPage: () => ({ error: new StructuredApiError(404, {}) }),
}));
vi.mock("./publicOrganizationsApi", () => ({
  usePublicOrganization: () => ({ data: legacy.legacy_organization }),
  usePublicOrganizationSpaces: (slug: string, page: number) => { spaceCalls(slug, page); return { data: { count: 25, next: "?page=2", previous: null, results: [
    { name: "Linked lab", slug: "lab", logo_url: null, canonical_url: "https://space.example/lab" },
  ] } }; },
  usePublicOrganizationEvents: (slug: string, page: number, period: string) => { eventCalls(slug, page, period); return { data: {
    period, count: period === "past" ? 1 : 25, next: period === "past" ? null : "?page=2", previous: null,
    results: period === "past" ? [archived] : [
      upcomingEvent("Paid class", "10000000-0000-4000-8000-000000000001", { slug: "lab", name: "Lab", logo_url: null }, "20.00"),
      upcomingEvent("Free class", "10000000-0000-4000-8000-000000000002", { slug: "elsewhere", name: "Unlinked venue", logo_url: null }, "0.00"),
    ],
  } }; },
}));
function show() {
  const client = new QueryClient();
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/o/builders"]}><Routes><Route path="/o/:organizationSlug" element={<PublicOrganizationPage />} /></Routes></MemoryRouter></QueryClientProvider>);
}
describe("organization P5 public collections", () => {
  it("keeps prices, canonical event actions and events hosted at unlinked venues", () => {
    show();
    expect(screen.getByText("€20.00")).toBeVisible(); expect(screen.getByText("Free", { selector: "dd" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Free class" })).toHaveAttribute("href", "https://space.example/e/10000000-0000-4000-8000-000000000002");
    expect(screen.getByText(/Hosted by Unlinked venue/)).toBeVisible();
    expect(screen.queryByRole("link", { name: "Unlinked venue" })).toBeNull();
    expect(screen.getByRole("link", { name: "Linked lab" })).toHaveAttribute("href", "https://space.example/lab");
  });
  it("shows upcoming before the card-only past archive and paginates collections independently", () => {
    show();
    const upcoming = screen.getByRole("region", { name: "Upcoming organization events" });
    const past = screen.getByRole("region", { name: "Past event archive" });
    expect(upcoming.compareDocumentPosition(past) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(past).getAllByRole("link")).toHaveLength(1);
    expect(within(past).queryByRole("link", { name: /Register|Archive workshop/ })).not.toBeInTheDocument();
    fireEvent.click(within(upcoming).getByRole("button", { name: /Next/ }));
    expect(eventCalls).toHaveBeenCalledWith("builders", 2, "upcoming");
    expect(eventCalls).toHaveBeenCalledWith("builders", 1, "past");
    expect(spaceCalls).not.toHaveBeenCalledWith("builders", 2);
  });
});
