import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
const QC = ({ children }: { children: ReactNode }) => <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>;
import { MemoryRouter, useParams } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import type { TenantBootstrap } from "./lib/api";
import { AppRoutes } from "./AppRoutes";

const { tenant, query } = vi.hoisted(() => ({ tenant: vi.fn(), query: vi.fn() }));
vi.mock("./lib/tenant", () => ({ useTenant: tenant }));
vi.mock("./features/inventory/usePublicInventory", () => ({ useTenantBootstrap: query }));
vi.mock("./features/members/MemberBorrowingHistoryPage", () => ({ MemberBorrowingHistoryPage: () => <h1>Own borrowing history</h1> }));
vi.mock("./features/inventory/PublicInventoryPage", () => ({ PublicInventoryPage: () => <h1>Inventory listing</h1> }));
vi.mock("./features/NotFoundPage", () => ({ NotFoundPage: () => <h1>Page unavailable</h1> }));
vi.mock("./features/public/MakerspacePage", () => ({ MakerspacePage: () => <h1>Makerspace home</h1> }));
vi.mock("./features/publicPages/pageApi", () => ({ usePublicPage: () => ({ data: { canonical_url: "https://space.example/lab", title: "Lab" } }) }));
vi.mock("./features/events/PublicEventCodePage", () => ({ PublicEventCodePage: () => <h1>Short event {useParams().publicToken}</h1> }));
vi.mock("./features/events/PublicWebsiteDetailPage", () => ({ PublicWebsiteDetailPage: ({ view }: { view: string }) => <h1>Deep {view}</h1> }));
vi.mock("./features/publicPages/PublicHandlePage", () => ({ PublicHandlePage: () => <h1>Public handle {useParams().handle}</h1> }));
vi.mock("./features/inventory/PublicEventsPage", () => ({ PublicEventsPage: () => <h1>Events home</h1> }));
vi.mock("./features/bookings/PublicBookingsPage", () => ({ PublicBookingsPage: () => <h1>Bookings home</h1> }));
vi.mock("./features/inventory/PublicMachinesPage", () => ({ PublicMachinesPage: () => <h1>Machines home</h1> }));
vi.mock("./features/members/MemberArea", () => ({ MemberArea: () => <h1>Membership home</h1> }));
vi.mock("./features/inventory/PublicEventDetailPage", () => ({ PublicEventDetailPage: () => <h1>Event {useParams().publicToken}</h1> }));
vi.mock("./features/staff/StaffApp", () => ({ StaffApp: () => null }));
vi.mock("./features/staff/PlatformApps", () => ({ SuperadminPage: () => null }));
vi.mock("./features/kiosk/PublicDeskKioskPage", () => ({ PublicDeskKioskPage: () => null }));
vi.mock("./features/kiosk/ScannerPage", () => ({ ScannerPage: () => null }));

const core = ["public_inventory", "request_workflow", "staff_admin", "qr_management", "evidence_uploads", "scanner"];
function bootstrap(family: string): TenantBootstrap {
  return {
    makerspace: { id: 1, name: "Lab", slug: "lab", public_code: "LAB1", location: "", geofence_enabled: false,
      membership_policy: "request", public_site_enabled: true, public_inventory_enabled: true },
    modules: [...core, ...(family === "inventory" ? [] : [family])],
    features: family === "inventory" ? ["loans.enabled"] : [], workflows: [], edition: "makerspace",
    frontend: { type: "makerspace", hostname: "", allowed_origins: [] }, theme: {}, branding: {}, email_enabled: false,
    public_api: { base_url: "/api/v1", publishable_key: "pk_test", inventory_path: "" },
  };
}
function show(data: TenantBootstrap, mode: "single" | "central" = "central", path?: string) {
  tenant.mockReturnValue({ mode, bootstrap: mode === "single" ? data : null });
  query.mockReturnValue({ data });
  return render(<MemoryRouter initialEntries={[path ?? (mode === "single" ? "/" : "/m/lab")]}>
    <AppRoutes mode={mode} landing={<h1>Directory</h1>} />
  </MemoryRouter>, { wrapper: QC });
}
beforeEach(() => vi.clearAllMocks());

it.each(["single", "central"] as const)("registers short events before handle catch-all in %s mode", async mode => {
  show(bootstrap("events"), mode, "/e/12345678");
  expect(await screen.findByRole("heading", { name: "Short event 12345678" })).toBeVisible();
});
it.each(["single", "central"] as const)("dispatches the universal handle route in %s mode", async mode => {
  show(bootstrap("events"), mode, "/forge");
  expect(await screen.findByRole("heading", { name: "Public handle forge" })).toBeVisible();
});
it("keeps the makerspace overview as the events-only home", async () => {
  show(bootstrap("events"));
  expect(await screen.findByRole("heading", { name: "Makerspace home" })).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Events home" })).toBeNull();
});

it.each(["single", "central"] as const)("preserves the programme deep links in %s mode", async mode => {
  show(bootstrap("events"), mode, mode === "single" ? "/events/token/schedule" : "/m/lab/events/token/schedule");
  expect(await screen.findByRole("heading", { name: "Deep schedule" })).toBeVisible();
});

it.each(["events", "machines", "membership", "bookings"])("routes an %s-only tenant to its overview on a shared deployment", async (family) => {
  show(bootstrap(family));
  expect(await screen.findByRole("heading", { name: "Makerspace home" })).toBeVisible();
  expect(screen.queryByText("Inventory listing")).toBeNull();
});

it("routes a catalogue tenant to the composed makerspace page", async () => {
  show(bootstrap("inventory"));
  expect(await screen.findByRole("heading", { name: "Makerspace home" })).toBeVisible();
});

it("composes the makerspace page for an automatic multi-family home", async () => {
  const data = bootstrap("events"); data.modules.push("bookings");
  show(data);
  expect(await screen.findByRole("heading", { name: "Makerspace home" })).toBeVisible();
});

it("treats an explicit inventory landing as the makerspace page", async () => {
  const data = bootstrap("inventory"); data.modules.push("events"); data.makerspace.public_landing_page = "inventory";
  show(data);
  expect(await screen.findByRole("heading", { name: "Makerspace home" })).toBeVisible();
});

it("keeps old ?space= home links on the bookings page", async () => {
  const data = bootstrap("inventory"); data.modules.push("bookings");
  show(data, "central", "/m/lab?space=room-a");
  expect(await screen.findByRole("heading", { name: "Bookings home" })).toBeVisible();
});

it("keeps the overview independent of edition and saved shortcut choice", async () => {
  const data = bootstrap("events"); data.modules.push("bookings"); data.edition = "events";
  data.makerspace.public_landing_page = "bookings";
  show(data, "single");
  expect(await screen.findByText("Makerspace home")).toBeVisible();
});

it("falls back when the saved landing family is disabled", async () => {
  const data = bootstrap("machines"); data.makerspace.public_landing_page = "inventory";
  show(data);
  expect(await screen.findByText("Makerspace home")).toBeVisible();
});

it("hides the catalogue when its publication flag is off", async () => {
  const data = bootstrap("inventory"); data.modules.push("events"); data.makerspace.public_inventory_enabled = false;
  show(data);
  expect(await screen.findByText("Makerspace home")).toBeVisible();
});

it("renders no family when the public site is off", () => {
  const data = bootstrap("events"); data.makerspace.public_site_enabled = false;
  show(data);
  expect(screen.getByText("Lab hasn't published anything yet. Check back soon.")).toBeVisible();
});

it.each(["single", "central"] as const)("registers the lazy event detail in %s routing", async (mode) => {
  show(bootstrap("events"), mode, mode === "single" ? "/events/abc123" : "/m/lab/events/abc123");
  expect(await screen.findByRole("heading", { name: "Event abc123" })).toBeVisible();
});

it("waits for bootstrap before selecting a family", () => {
  tenant.mockReturnValue({ mode: "central", bootstrap: null }); query.mockReturnValue({ data: undefined });
  render(<MemoryRouter initialEntries={["/m/lab"]}><AppRoutes mode="central" landing={null} /></MemoryRouter>, { wrapper: QC });
  expect(screen.getByText("Opening Space Works…")).toBeVisible();
  expect(screen.queryByText("Makerspace home")).toBeNull();
});

it("keeps unavailable-page links in the single-space URL family", () => {
  const data = bootstrap("events"); data.makerspace.public_site_enabled = false;
  show(data, "single");
  expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/member");
  expect(screen.getByRole("link", { name: "Lab home" })).toHaveAttribute("href", "/");
});

it.each(["single", "central"] as const)("routes inventory separately from the overview in %s mode", async mode => {
  show(bootstrap("inventory"), mode, mode === "single" ? "/inventory" : "/m/lab/inventory");
  expect(await screen.findByRole("heading", { name: "Inventory listing" })).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Makerspace home" })).toBeNull();
});

it.each(["site", "publication", "loans", "module"])("does not mount inventory when its %s gate is off", async gate => {
  const data = bootstrap("inventory");
  if (gate === "site") data.makerspace.public_site_enabled = false;
  if (gate === "publication") data.makerspace.public_inventory_enabled = false;
  if (gate === "loans") data.features = [];
  if (gate === "module") data.modules = [];
  show(data, "central", "/m/lab/inventory");
  expect(await screen.findByRole("heading", { name: "Page unavailable" })).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Inventory listing" })).toBeNull();
});

it("still shows an overview for a published shop-only tenant", async () => {
  const data = bootstrap("shop");
  show(data);
  expect(await screen.findByRole("heading", { name: "Makerspace home" })).toBeVisible();
});


it.each(["single", "central"] as const)("registers the account-only borrowing history route in %s mode", async mode => {
  show(bootstrap("inventory"), mode, mode === "single" ? "/member/loans/history" : "/m/lab/member/loans/history");
  expect(await screen.findByRole("heading", { name: "Own borrowing history" })).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Membership home" })).toBeNull();
});
