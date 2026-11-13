import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { PublicActionCard } from "../../components/layouts/PublicActionCard";
import { PublicInventoryPage } from "./PublicInventoryPage";

const mock = vi.hoisted(() => ({ member: vi.fn(), desktop: true }));
vi.mock("../../lib/api", () => ({ memberRequest: mock.member, staffRequest: vi.fn() }));
vi.mock("../../lib/api/sessionTokens", () => ({ hasSessionIdentity: () => true, getSessionOwner: () => "1" }));
vi.mock("./useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: "1" }) }));
vi.mock("../../components/layouts/useLayoutMedia", () => ({ useLayoutMedia: () => mock.desktop }));
vi.mock("../../lib/tenant", () => ({ useTenant: () => ({ mode: "single", slug: "forge", modules: new Set(["inventory"]), bootstrap: { makerspace: { id: 4, name: "Forge" }, branding: {}, features: ["inventory.consumables"] } }), useTenantPath: () => (path: string) => `/m/forge/${path}`,
  useOptionalTenant: () => ({ mode: "single" }), tenantPath: (_mode: string, _slug: string, path = "") => `/${path}` }));
vi.mock("../../lib/useTenantBranding", () => ({ useTenantBranding: () => ({}) }));
vi.mock("./usePublicInventory", () => ({ useTenantBootstrap: () => ({}), usePublicCategories: () => ({ data: [] }), usePublicInventory: () => ({ data: { results: [], count: 0 }, isLoading: false, isError: false, isFetching: false }) }));
vi.mock("./publicInventory/useInventoryCart", () => ({ useInventoryCart: () => ({ cart: {}, selectedItems: [], incrementItem: vi.fn(), decrementItem: vi.fn(), clearCart: vi.fn() }) }));
vi.mock("./useRequestDraft", () => ({ useRequestDraft: () => ({ requestedFor: "", setRequestedFor: vi.fn(), submitted: false, setSubmitted: vi.fn(), website: "", setWebsite: vi.fn(), pickup: { from: "", until: "" }, setPickup: vi.fn() }) }));
vi.mock("./useContactRequest", () => ({ useContactRequest: () => ({ ready: true, payload: {}, details: {}, clear: vi.fn() }) }));
vi.mock("./ProductQuickViewModal", () => ({ ProductQuickViewModal: () => null }));
vi.mock("./api", () => ({ submitPublicRequest: vi.fn() }));

it("reaches a consumable-only plan through the catalogue action card with lending off", async () => {
  mock.desktop = true;
  mock.member.mockReset(); mock.member.mockImplementation((path: string) => {
    if (path === "/auth/me") return Promise.resolve({ id: 1 });
    if (path.includes("equipment-kits")) return Promise.resolve({ results: [{ id: 9, name: "Materials", version: 2, lines: [{ product_id: 3, display_name: "Glue", quantity_per_person: 1, kind: "consumable" }] }], next: null, previous: null });
    return Promise.resolve({ kind: "consumable_plan", plan_id: 12, replayed: false });
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><PublicInventoryPage embedded={({ aside }) => <PublicActionCard {...aside} />} /></MemoryRouter></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Materials" }));
  fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "Workshop" } });
  fireEvent.click(screen.getByRole("button", { name: "Save plan" }));
  await screen.findByText("Consumable plan saved. No equipment was issued or stock used.");
  const call = mock.member.mock.calls.find(row => String(row[0]).endsWith("/requests/contextual"));
  expect(call).toBeDefined();
  expect(JSON.parse(call![1].body)).toMatchObject({ kit: { id: 9, version: 2 }, event_registration_id: null, booking_token: null });
  expect(JSON.parse(call![1].body)).not.toHaveProperty("items");
  await waitFor(() => expect(mock.member.mock.calls.filter(row => String(row[0]).endsWith("/requests/contextual"))).toHaveLength(1));
});

it("reopens the mobile sheet unlocked when its original request succeeds while closed", async () => {
  mock.desktop = false;
  let resolveRequest!: (value: unknown) => void;
  mock.member.mockReset(); mock.member.mockImplementation((path: string) => {
    if (path === "/auth/me") return Promise.resolve({ id: 1 });
    if (path.includes("equipment-kits")) return Promise.resolve({ results: [{ id: 9, name: "Materials", version: 2, lines: [{ product_id: 3, display_name: "Glue", quantity_per_person: 1, kind: "consumable" }] }], next: null, previous: null });
    return new Promise(resolve => { resolveRequest = resolve; });
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><PublicInventoryPage embedded={({ aside }) => <PublicActionCard {...aside} />} /></MemoryRouter></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Review request" }));
  fireEvent.click(await screen.findByRole("button", { name: "Materials" }));
  fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "Workshop" } });
  fireEvent.click(screen.getByRole("button", { name: "Save plan" }));
  await waitFor(() => expect(resolveRequest).toBeDefined());
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  expect(screen.queryByRole("button", { name: "Save plan" })).toBeNull();
  await act(async () => { resolveRequest({ kind: "consumable_plan", plan_id: 12, replayed: false }); });
  await waitFor(() => expect(mock.member.mock.calls.filter(row => String(row[0]).endsWith("/requests/contextual"))).toHaveLength(1));
  fireEvent.click(screen.getByRole("button", { name: "Review request" }));
  expect(await screen.findAllByText("Consumable plan saved. No equipment was issued or stock used.")).toHaveLength(1);
  fireEvent.click(await screen.findByRole("button", { name: "Materials" }));
  fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "Another workshop" } });
  expect(screen.getByRole("button", { name: "Save plan" })).not.toBeDisabled();
  expect(mock.member.mock.calls.filter(row => String(row[0]).endsWith("/requests/contextual"))).toHaveLength(1);
});
