import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { PublicActionCard } from "../../components/layouts/PublicActionCard";
import { PublicInventoryPage } from "./PublicInventoryPage";

const mock = vi.hoisted(() => ({ member: vi.fn() }));
vi.mock("../../lib/api", () => ({ memberRequest: mock.member, staffRequest: vi.fn() }));
vi.mock("../../lib/api/sessionTokens", () => ({ hasSessionIdentity: () => true, getSessionOwner: () => "1" }));
vi.mock("./useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: "1" }) }));
vi.mock("../../components/layouts/useLayoutMedia", () => ({ useLayoutMedia: () => false }));
vi.mock("../../lib/tenant", () => ({ useTenant: () => ({ mode: "single", slug: "forge", modules: new Set(["request_workflow"]), bootstrap: { makerspace: { id: 4, name: "Forge" }, branding: {}, features: ["loans.enabled"] } }), useTenantPath: () => (path: string) => `/m/forge/${path}`,
  useOptionalTenant: () => ({ mode: "single" }), tenantPath: (_mode: string, _slug: string, path = "") => `/${path}` }));
vi.mock("../../lib/useTenantBranding", () => ({ useTenantBranding: () => ({}) }));
vi.mock("./usePublicInventory", () => ({ useTenantBootstrap: () => ({}), usePublicCategories: () => ({ data: [] }), usePublicInventory: () => ({ data: { results: [{ id: 3, name: "Drill", availability: null }], count: 1 }, isLoading: false, isError: false, isFetching: false }) }));
vi.mock("./ProductCard", () => ({ ProductCard: ({ onIncrement }: { onIncrement: () => void }) => <button onClick={onIncrement}>Add Drill</button> }));
vi.mock("./ProductQuickViewModal", () => ({ ProductQuickViewModal: () => null }));
vi.mock("./useContactRequest", () => ({ useContactRequest: () => ({ ready: true, payload: {}, details: undefined, clear: vi.fn() }) }));
vi.mock("../payments/PricePreview", () => ({ PricePreview: () => null }));
vi.mock("./api", () => ({ submitPublicRequest: vi.fn() }));

it("clears the real page cart and draft when contextual success arrives while the sheet is closed", async () => {
  let finish!: (body: unknown) => void;
  mock.member.mockReset(); mock.member.mockImplementation((path: string) => {
    if (path === "/auth/me") return Promise.resolve({ id: 1, username: "member", email: "member@example.test", display_name: "Member", phone: "", email_verified: true, kind: "person" });
    if (path.includes("equipment-kits")) return Promise.resolve({ results: [], next: null, previous: null });
    if (path.endsWith("/requests/contextual")) return new Promise(resolve => { finish = resolve; });
    return Promise.resolve({ results: [] });
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><PublicInventoryPage embedded={({ body, aside }) => <>{body}<PublicActionCard {...aside} /></>} /></MemoryRouter></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Add Drill" }));
  fireEvent.click(screen.getByRole("button", { name: "Review request" }));
  fireEvent.change(await screen.findByPlaceholderText("What do you need these items for?"), { target: { value: "Workshop" } });
  fireEvent.click(await screen.findByRole("button", { name: "Submit equipment request" }));
  await waitFor(() => expect(finish).toBeDefined());
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  await act(async () => { finish({ kind: "request", public_token: "private-token", status: "pending_approval", replayed: false }); });
  fireEvent.click(screen.getByRole("button", { name: "Review request" }));
  expect((await screen.findByPlaceholderText("What do you need these items for?")) as HTMLInputElement).toHaveValue("");
  expect(screen.getByRole("button", { name: "Submit equipment request" })).toBeDisabled();
  expect(screen.queryByText("Drill", { selector: "li" })).toBeNull();
});

it("retains one contextual consumable-plan confirmation after the sheet closes", async () => {
  let finish!: (body: unknown) => void;
  mock.member.mockReset(); mock.member.mockImplementation((path: string) => {
    if (path === "/auth/me") return Promise.resolve({ id: 1, username: "member", email: "member@example.test", display_name: "Member", phone: "", email_verified: true, kind: "person" });
    if (path.includes("equipment-kits")) return Promise.resolve({ results: [{ id: 9, name: "Materials", version: 2, lines: [{ product_id: 3, display_name: "Glue", quantity_per_person: 1, kind: "consumable" }] }], next: null, previous: null });
    if (path.endsWith("/requests/contextual")) return new Promise(resolve => { finish = resolve; });
    return Promise.resolve({ results: [] });
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><PublicInventoryPage embedded={({ body, aside }) => <>{body}<PublicActionCard {...aside} /></>} /></MemoryRouter></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Add Drill" }));
  fireEvent.click(screen.getByRole("button", { name: "Review request" }));
  fireEvent.change(await screen.findByPlaceholderText("What do you need these items for?"), { target: { value: "Workshop" } });
  fireEvent.click(await screen.findByRole("button", { name: "Materials" }));
  fireEvent.click(screen.getByRole("button", { name: "Submit equipment request" }));
  await waitFor(() => expect(finish).toBeDefined());
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  await act(async () => { finish({ kind: "consumable_plan", plan_id: 12, replayed: false }); });
  fireEvent.click(screen.getByRole("button", { name: "Review request" }));
  expect(await screen.findAllByText("Consumable plan saved. No equipment was issued or stock used.")).toHaveLength(1);
  expect(mock.member.mock.calls.filter(row => String(row[0]).endsWith("/requests/contextual"))).toHaveLength(1);
});
