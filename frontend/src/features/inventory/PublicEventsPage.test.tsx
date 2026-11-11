import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PublicEventsPage } from "./PublicEventsPage";
import { TenantProvider } from "../../lib/tenant";

const { tenantPublicRequest } = vi.hoisted(() => ({ tenantPublicRequest: vi.fn() }));
vi.mock("../../lib/api", async () => ({
  ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), tenantPublicRequest,
}));
vi.mock("./usePublicInventory", () => ({ useTenantBootstrap: () => ({ data: undefined }) }));

function event(title: string, amount: string, approval = false) {
  return {
    public_token: title, title, description: "", starts_at: "2026-11-01T10:00:00Z", ends_at: "2026-11-01T12:00:00Z",
    location: "Lab", capacity: 5, availability: "Available", payment_amount: amount, currency: "inr",
    registration_requires_approval: approval, registration_open: true, effective_registration_cutoff_at: null,
    image_url: null, status: "published", custom_form: null, series: null,
  };
}

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/m/lab/events"]}><TenantProvider><Routes><Route path="/m/:slug/events" element={<PublicEventsPage />} /></Routes></TenantProvider></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => { tenantPublicRequest.mockReset(); });

describe("public event prices", () => {
  it("excludes unavailable member-only tickets from the free-events filter", async () => {
    tenantPublicRequest.mockResolvedValue([
      { ...event("Members only", "0"), ticket_types: [], ticket_selection_required: true },
      event("Free public workshop", "0"),
    ]);
    show();
    await screen.findByText("Members only", { selector: ".title-section" });
    fireEvent.change(screen.getByLabelText("Filter"), { target: { value: "free" } });
    expect(screen.queryByText("Members only", { selector: ".title-section" })).toBeNull();
    expect(screen.getByText("Free public workshop", { selector: ".title-section" })).toBeVisible();
  });

  it("shows paid and free prices before opening registration", async () => {
    tenantPublicRequest.mockResolvedValue([event("Paid", "125.50"), event("Free class", "0.00")]);
    show();
    expect(await screen.findByText("₹125.50")).toBeVisible();
    expect(screen.getByText("Free")).toBeVisible();
    expect(screen.queryByRole("form")).toBeNull();
  });

  it("keeps the price visible beside an approval application form", async () => {
    tenantPublicRequest.mockResolvedValue([event("Reviewed", "80.00", true)]);
    show();
    await screen.findByText("₹80.00");
    expect(screen.getByRole("link", { name: "Apply" })).toHaveAttribute("href", "/m/lab/events/Reviewed");
    expect(screen.getByText("₹80.00")).toBeVisible();
  });
  it("filters by tenant category and tag and links each event detail", async () => {
    const wood = { ...event("Wood", "0"), category: { id: 1, name: "Workshops", slug: "workshops" }, tags: ["wood"] };
    const social = { ...event("Social", "0"), category: { id: 2, name: "Meetups", slug: "meetups" }, tags: ["community"] };
    tenantPublicRequest.mockResolvedValue([wood, social]);
    show();
    await screen.findByText("Wood", { selector: ".title-section" });
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "workshops" } });
    expect(screen.queryByText("Social", { selector: ".title-section" })).toBeNull();
    expect(screen.getByText("Wood", { selector: ".title-section" }).closest("a")).toHaveAttribute("href", "/m/lab/events/Wood");
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Tag"), { target: { value: "community" } });
    expect(screen.queryByText("Wood", { selector: ".title-section" })).toBeNull();
    expect(screen.getByText("Social", { selector: ".title-section" })).toBeVisible();
  });

  it("shows each event's cover, description, status, capacity and closing time", async () => {
    tenantPublicRequest.mockResolvedValue([
      { ...event("Laser basics", "0"), description: "Learn to cut acrylic.", image_url: "https://img.test/laser.png" },
      { ...event("Closed class", "0"), capacity: null, registration_open: false, effective_registration_cutoff_at: "2026-10-30T10:00:00Z" },
    ]);
    show();
    await screen.findByText("Laser basics", { selector: ".title-section" });
    expect(document.querySelector('img[src="https://img.test/laser.png"]')).not.toBeNull();
    expect(screen.getByText("Learn to cut acrylic.")).toBeVisible();
    expect(screen.getAllByText("Published")).toHaveLength(2);
    expect(screen.getByText("5")).toBeVisible();
    expect(screen.getByText("Unlimited")).toBeVisible();
    expect(screen.getByText(/^Registration closed · /)).toBeVisible();
    expect(screen.getByRole("link", { name: "View event" })).toHaveAttribute("href", "/m/lab/events/Closed class");
  });

});
