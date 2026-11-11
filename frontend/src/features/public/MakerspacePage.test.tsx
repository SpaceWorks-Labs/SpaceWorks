import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { TenantBootstrap } from "../../lib/api";
import { expectNoA11yViolations } from "../../test/axe";
import { emptyWeek } from "../staff/makerspaceProfileForm";
import { MakerspacePage } from "./MakerspacePage";
import { PublicInventoryRoute } from "../inventory/PublicInventoryRoute";

const state = vi.hoisted(() => ({ bootstrap: null as unknown as TenantBootstrap, products: [] as unknown[], published: null as unknown, inventoryRead: vi.fn(), categoriesRead: vi.fn() }));
const { tenantPublicRequest } = vi.hoisted(() => ({ tenantPublicRequest: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), tenantPublicRequest }));
vi.mock("../../lib/tenant", () => ({
  useTenant: () => ({ mode: "central", slug: "", modules: new Set(), bootstrap: null }),
  useTenantPath: () => (subpath = "") => `/m/lab${subpath ? `/${subpath}` : ""}`,
}));
vi.mock("../inventory/usePublicInventory", () => ({
  useTenantBootstrap: () => ({ data: state.bootstrap }),
  usePublicCategories: () => { state.categoriesRead(); return { data: [] }; },
  usePublicInventory: () => { state.inventoryRead(); return { data: { results: state.products, count: state.products.length }, isLoading: false, isError: false, refetch: vi.fn() }; },
}));
vi.mock("../publicPages/pageApi", async () => ({ ...await vi.importActual<typeof import("../publicPages/pageApi")>("../publicPages/pageApi"), usePublicPage: () => ({ data: state.published }) }));
vi.mock("../inventory/PublicRequestPanel", () => ({ PublicRequestPanel: () => <p>Request panel content</p> }));

function bootstrap(modules: string[], overrides: Partial<TenantBootstrap["makerspace"]> = {}): TenantBootstrap {
  return {
    makerspace: { id: 1, name: "Lab", slug: "lab", public_code: "LAB1", location: "21 Cusat Road, Kochi", geofence_enabled: false,
      membership_policy: "open", public_site_enabled: true, public_inventory_enabled: true, timezone: "Asia/Kolkata",
      map_url: "https://maps.example.test/lab", opening_hours: { weekly: { ...emptyWeek(), mon: [{ start: "09:00", end: "17:00" }] }, exceptions: {} }, ...overrides },
    modules, features: modules.includes("public_inventory") ? ["loans.enabled"] : [], workflows: [], edition: "makerspace",
    frontend: { type: "makerspace", hostname: "", allowed_origins: [] }, theme: {}, branding: { support_email: "help@lab.test" }, email_enabled: false,
    public_api: { base_url: "/api/v1", publishable_key: "pk_test", inventory_path: "" },
  };
}
const ALL = ["public_inventory", "request_workflow", "events", "machines", "bookings", "membership"];

function event(title: string, extra: Record<string, unknown> = {}) {
  return { public_token: title.toLowerCase().replace(/\s+/g, "-"), title, description: "", starts_at: "2099-10-17T04:30:00Z", ends_at: "2099-10-17T08:00:00Z",
    location: "TinkerSpace, Kochi", capacity: 5, availability: "Available", payment_amount: "0.00", currency: "inr",
    registration_requires_approval: false, registration_open: true, effective_registration_cutoff_at: null,
    image_url: null, status: "published", custom_form: null, series: null, ...extra };
}
const space = { public_token: "room-a", name: "Room A", kind: "meeting", description: "", capacity: 8, location: "First floor", image_url: "",
  approval_mode: "instant", custom_form: null, show_public_availability: true, show_public_booker_names: false };

function respond(events: unknown[] | Error = [], spaces: unknown[] = [space]) {
  tenantPublicRequest.mockImplementation((_slug: string, path: string) => {
    if (path.includes("/events/")) return events instanceof Error ? Promise.reject(events) : Promise.resolve(events);
    if (path.includes("/spaces/")) return Promise.resolve(spaces);
    return Promise.reject(new Error(`unexpected ${path}`));
  });
}
function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/m/lab"]}><Routes><Route path="/m/:slug" element={<MakerspacePage />} /><Route path="/m/:slug/inventory" element={<PublicInventoryRoute />} /></Routes></MemoryRouter></QueryClientProvider>);
}
const sections = (container: HTMLElement) => [...container.querySelectorAll("[data-section]")].map((node) => node.getAttribute("data-section"));

beforeEach(() => {
  tenantPublicRequest.mockReset();
  state.inventoryRead.mockClear(); state.categoriesRead.mockClear(); state.published = null;
  state.bootstrap = bootstrap(ALL);
  state.products = [{ id: 1, name: "Soldering iron", description: "Hakko", availability: { mode: "status_only", label: "Available" } }];
});

describe("makerspace page", () => {
  it("puts the overview header first, then featured activities and enabled-area links without an inventory listing", async () => {
    respond([event("Hacktoberfest Meetup")]);
    const { container } = show();
    await screen.findByRole("heading", { name: "Featured activities" });
    await screen.findByRole("heading", { name: "Book a space" });
    const h1 = screen.getByRole("heading", { level: 1, name: "Lab" });
    expect(h1.compareDocumentPosition(screen.getByRole("heading", { name: "Featured activities" })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(sections(container)).toEqual(["featured", "explore", "machines", "spaces", "membership", "contact"]);
    expect(screen.getByRole("navigation", { name: "Quick actions" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Browse inventory" })).toHaveAttribute("href", "/m/lab/inventory");
    expect(screen.queryByRole("button", { name: "Review request" })).toBeNull();
    expect(screen.queryByLabelText("Search inventory")).toBeNull();
    expect(screen.queryByText("Soldering iron")).toBeNull();
    expect(state.inventoryRead).not.toHaveBeenCalled();
    expect(state.categoriesRead).not.toHaveBeenCalled();
  });

  it("meets the WCAG 2.1 AA floor with every section rendered", async () => {
    respond([event("Meetup", { category: { id: 1, name: "Bootcamp", slug: "bootcamp" }, image_url: "https://img.test/banner.png" })]);
    const { container } = show();
    await screen.findByRole("article", { name: "Meetup" });
    await screen.findByRole("heading", { name: "Book a space" });
    await expectNoA11yViolations(container);
  });

  it("shows location, directions and today's hours in the makerspace's zone", () => {
    respond();
    show();
    const header = screen.getByRole("banner", { name: "Lab" });
    expect(within(header).getByText(/21 Cusat Road, Kochi/)).toBeVisible();
    expect(within(header).getByRole("link", { name: "Get directions" })).toHaveAttribute("href", "https://maps.example.test/lab");
    expect(screen.getByRole("table", { name: "Weekly opening hours" })).toBeInTheDocument();
  });

  it("renders a featured card with date, time, venue, tags, price and a register link to the event", async () => {
    respond([event("Hacktoberfest Meetup", { category: { id: 1, name: "Bootcamp", slug: "bootcamp" }, audience_label: "Public", tags: ["offline"],
      image_url: "https://img.test/banner.png", payment_amount: "250.00" })]);
    show();
    const rail = await screen.findByRole("list", { name: "Upcoming events" });
    const card = within(rail).getByRole("article", { name: "Hacktoberfest Meetup" });
    expect(within(card).getByText((_, node) => node?.tagName === "TIME" && node.textContent?.replace(/\s/g, " ") === "17 Oct · 10:00 AM – 1:30 PM")).toBeVisible();
    expect(within(card).getByText("TinkerSpace, Kochi")).toBeVisible();
    expect(within(card).getAllByRole("listitem").map((chip) => chip.textContent)).toEqual(["Bootcamp", "Public", "offline"]);
    expect(within(card).getByText("₹250.00")).toBeVisible();
    expect(within(card).getByRole("link", { name: "Register" })).toHaveAttribute("href", "/m/lab/events/hacktoberfest-meetup");
    expect(card.querySelector("img")).toHaveAttribute("alt", "");
  });

  it("labels free events and links back to the full events page", async () => {
    respond([event("Open night")]);
    show();
    const card = await screen.findByRole("article", { name: "Open night" });
    expect(within(card).getByText("Free")).toBeVisible();
    expect(screen.getByRole("link", { name: "All events" })).toHaveAttribute("href", "/m/lab/events");
  });

  it("hides Featured activities when nothing is upcoming", async () => {
    respond([event("Long gone", { starts_at: "2001-01-01T10:00:00Z", ends_at: "2001-01-01T12:00:00Z" })]);
    const { container } = show();
    await screen.findByRole("heading", { name: "Book a space" });
    await waitFor(() => expect(tenantPublicRequest).toHaveBeenCalledWith("lab", expect.stringContaining("/events/")));
    expect(screen.queryByRole("heading", { name: "Featured activities" })).toBeNull();
    expect(sections(container)[0]).toBe("explore");
  });

  it("asks for no events and shows no rail when the events module is off", async () => {
    state.bootstrap = bootstrap(ALL.filter((key) => key !== "events"));
    respond([event("Should not show")]);
    show();
    await screen.findByRole("heading", { name: "Book a space" });
    expect(screen.queryByRole("heading", { name: "Featured activities" })).toBeNull();
    expect(tenantPublicRequest.mock.calls.some(([, path]) => String(path).includes("/events/"))).toBe(false);
    expect(screen.queryByRole("link", { name: "See events" })).toBeNull();
  });

  it("drops the catalogue and its request card when the public inventory is unpublished", async () => {
    state.bootstrap = bootstrap(ALL, { public_inventory_enabled: false });
    respond([event("Meetup")]);
    const { container } = show();
    await screen.findByRole("heading", { name: "Featured activities" });
    expect(sections(container)).not.toContain("inventory");
    expect(screen.queryByRole("button", { name: "Review request" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Browse inventory" })).toBeNull();
  });

  it("omits machines, spaces and membership when those modules are off, and spaces when none are published", async () => {
    state.bootstrap = bootstrap(["public_inventory", "request_workflow", "events", "bookings"]);
    respond([], []);
    const { container } = show();
    await waitFor(() => expect(tenantPublicRequest).toHaveBeenCalledWith("lab", expect.stringContaining("/spaces/")));
    await waitFor(() => expect(sections(container)).toEqual(["explore", "contact"]));
  });

  it("offers a retry when upcoming events fail to load", async () => {
    respond(new Error("down"));
    show();
    // A network failure is retried twice (1s, 2s) before the section gives up.
    expect(await screen.findByRole("alert", {}, { timeout: 6000 })).toHaveTextContent("Couldn't load upcoming events.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeVisible();
  }, 10_000);

  it("matches the join call to the membership policy", async () => {
    state.bootstrap = bootstrap(ALL, { membership_policy: "invite_only" });
    respond();
    show();
    const membership = await screen.findByRole("region", { name: "Membership" });
    expect(within(membership).getByText(/by invitation/)).toBeVisible();
    expect(within(membership).getByRole("link", { name: "Member sign in" })).toHaveAttribute("href", "/m/lab/member");
  });

  it("renders only public fields: no storage locations, box ids, QR codes, hidden counts or registrant data", async () => {
    state.products = [
      { id: 1, name: "Soldering iron", description: "Hakko", availability: null, storage_location: "Shelf B3", box_id: "BOX-77", qr_code: "QR-SECRET" },
      { id: 2, name: "Multimeter", description: "", availability: { mode: "status_only", label: "Limited" }, count: 4 },
    ];
    respond([event("Meetup", { show_registration_count: false, registration_count: 42, registrations: [{ email: "someone@lab.test" }] })]);
    const { container } = show();
    await screen.findByRole("article", { name: "Meetup" });
    for (const secret of ["Shelf B3", "BOX-77", "QR-SECRET", "someone@lab.test"]) expect(container.textContent).not.toContain(secret);
    expect(within(screen.getByRole("region", { name: "Featured activities" })).queryByText("42")).toBeNull();
    expect(screen.queryByRole("region", { name: "Inventory" })).toBeNull();
    expect(state.inventoryRead).not.toHaveBeenCalled();
  });
});

it("uses the configured banner above the makerspace heading without inventing an image when unset", () => {
  respond();
  state.bootstrap.makerspace.cover_image_url = "https://cdn.test/public-images/lab/banner.webp";
  const view = show();
  const banner = view.container.querySelector('img[src="https://cdn.test/public-images/lab/banner.webp"]');
  expect(banner).toBeInTheDocument();
  expect(banner!.compareDocumentPosition(screen.getByRole("heading", { level: 1, name: "Lab" })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  view.unmount();
  state.bootstrap.makerspace.cover_image_url = null;
  const empty = show();
  expect(empty.container.querySelector('header[aria-labelledby="makerspace-title"] img')).toBeNull();
  expect(screen.getByRole("heading", { level: 1, name: "Lab" })).toBeVisible();
});

it("preserves a released custom homepage and functional activities while the makerspace banner takes precedence", async () => {
  respond([event("Custom home event")]);
  state.bootstrap.makerspace.cover_image_url = "https://cdn.test/public-images/lab/banner.webp";
  state.published = { schema_version: 1, kind: "makerspace", canonical_url: "https://space.test/lab", title: "Welcome to our lab", description: "Our published welcome", publication_token: "published-token",
    cover: { url: "https://cdn.test/public-pages/editor-cover.webp", alt: "Editorial cover" },
    presentation: { accent_choice: "inherit", resolved_theme: { theme_config: {} } },
    sections: [{ id: "functional", type: "functional_content", enabled: true, payload: { links: [] } }] };
  const { container } = show();
  expect(screen.getByRole("heading", { level: 1, name: "Welcome to our lab" })).toBeVisible();
  expect(await screen.findByRole("article", { name: "Custom home event" })).toBeVisible();
  expect(container.querySelector('img[src="https://cdn.test/public-images/lab/banner.webp"]')).toBeInTheDocument();
  const hero = screen.getByRole("heading", { level: 1, name: "Welcome to our lab" }).closest("header")!;
  expect(within(hero).queryByRole("img", { name: "Editorial cover" })).toBeNull();
  expect(hero.querySelector('img[src="https://cdn.test/public-images/lab/banner.webp"]')).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Browse inventory" })).toHaveAttribute("href", "/m/lab/inventory");
  expect(state.inventoryRead).not.toHaveBeenCalled();
  expect(document.head.querySelector('link[rel="canonical"]')).toHaveAttribute("href", "https://space.test/lab");
});

it("keeps a saved available home choice as the primary shortcut while preserving the overview", () => {
  respond();
  state.bootstrap.makerspace.public_landing_page = "bookings";
  show();
  const quick = screen.getByRole("navigation", { name: "Quick actions" });
  expect(within(quick).getAllByRole("link")[0]).toHaveAccessibleName("Book a space");
  expect(screen.getByRole("heading", { level: 1, name: "Lab" })).toBeVisible();
  expect(state.inventoryRead).not.toHaveBeenCalled();
});

it("navigates from the overview to inventory and keeps the existing request flow there", async () => {
  respond();
  show();
  expect(state.inventoryRead).not.toHaveBeenCalled();
  const nav = screen.getByRole("navigation", { name: "Public navigation" });
  fireEvent.click(within(nav).getByRole("link", { name: "Inventory" }));
  expect(await screen.findByRole("heading", { level: 1, name: "Inventory" })).toBeVisible();
  expect(screen.getByLabelText("Search inventory")).toBeVisible();
  expect(screen.getByText("Soldering iron")).toBeVisible();
  expect(state.inventoryRead).toHaveBeenCalled();
  expect(screen.queryByRole("heading", { name: "Explore this space" })).toBeNull();
  expect(screen.queryByRole("heading", { name: "Featured activities" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Review request" }));
  expect(screen.getByRole("dialog", { name: "Your request" })).toHaveTextContent("Request panel content");
});
