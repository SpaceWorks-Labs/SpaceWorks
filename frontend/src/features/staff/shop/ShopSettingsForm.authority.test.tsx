import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ShopSettingsForm } from "./ShopSettingsForm";
import { SHOP_SETTING_DEFAULTS } from "./shopSettingsFields";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual("../../../lib/api"), staffRequest: request }));
const settingsPath = "/admin/makerspaces/7/shop/settings/";
const domainPath = "/admin/makerspace/7/domain-settings/shop";
const effectivePath = "/admin/makerspace/7/settings-authority/effective";
let manager = false;
let locked = new Set(["shop_online_hold_minutes"]);
let unavailable = false;
const permission = (key: string) => ({ key, editable: manager || !locked.has(key), locked: locked.has(key),
  via: manager ? "space_manager" : "fixed_exception", code: !manager && locked.has(key) ? "setting_locked" : null, lock_note: "" });
const domain = () => ({ domain: "shop", editable: true, settings: {}, setting_permissions: {}, features: [
  { key: "shop.online", label: "Online shop", description: "Take online orders.", parent_module: "shop",
    requires_features: [], enabled: false, available: true, editable: true, locked: false },
] });
beforeEach(() => {
  manager = false; unavailable = false; locked = new Set(["shop_online_hold_minutes"]); request.mockReset();
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === settingsPath) return { ...SHOP_SETTING_DEFAULTS, ...(init?.body ? JSON.parse(String(init.body)) : {}) };
    if (path === effectivePath) {
      if (unavailable) throw new Error("Authority unavailable");
      return { modules: [{ module: "shop", space_manager: manager, grant_id: null,
        keys: Object.keys(SHOP_SETTING_DEFAULTS).map(key => permission(`shop_${key}`)) }] };
    }
    if (path === domainPath) return domain();
    if (path.endsWith("/settings-authority/locks")) return {};
    throw new Error(`Unexpected path ${path}`);
  });
});
function show() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <ShopSettingsForm makerspaceId={7} />
  </QueryClientProvider>);
}

it("shows the Shop Manager's fixed settings access and saves only an unlocked change", async () => {
  show();
  expect(await screen.findByLabelText("Online hold (minutes)")).toBeDisabled();
  const note = screen.getByLabelText("Pickup note");
  expect(note).toBeEnabled();
  fireEvent.change(note, { target: { value: "Collect at the front desk." } });
  fireEvent.click(screen.getByRole("button", { name: "Save settings" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith(settingsPath,
    { method: "PATCH", body: JSON.stringify({ pickup_note: "Collect at the front desk." }) }));
  expect(screen.queryByRole("button", { name: /for managers$/ })).not.toBeInTheDocument();
});

it("offers existing Shop switches through their own domain endpoint", async () => {
  show();
  fireEvent.click(await screen.findByRole("checkbox", { name: /^Online shop/ }));
  await waitFor(() => expect(request).toHaveBeenCalledWith(domainPath,
    { method: "PATCH", body: JSON.stringify({ features: { "shop.online": true } }) }));
});

it("lets the Space Manager edit a locked setting and manage its exact existing lock key", async () => {
  manager = true; show();
  expect(await screen.findByLabelText("Online hold (minutes)")).toBeEnabled();
  const lock = screen.getByRole("button", { name: "Locked for managers Online hold (minutes)" });
  expect(lock).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(lock);
  await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/makerspace/7/settings-authority/locks",
    { method: "PUT", body: JSON.stringify({ setting_key: "shop_online_hold_minutes", locked: false }) }));
});

it("prevents invalid hold bounds and reminder ordering before a save", async () => {
  locked.clear(); show();
  const online = await screen.findByLabelText("Online hold (minutes)");
  expect(online).toHaveAttribute("min", "5"); expect(online).toHaveAttribute("max", "120");
  fireEvent.change(online, { target: { value: "4" } });
  expect(screen.getByRole("button", { name: "Save settings" })).toBeDisabled();
  expect(screen.getByRole("alert")).toHaveTextContent("between 5 and 120");
  fireEvent.change(online, { target: { value: "15" } });
  fireEvent.change(screen.getByLabelText("Second pickup reminder (days)"), { target: { value: "3" } });
  expect(screen.getByRole("button", { name: "Save settings" })).toBeDisabled();
  expect(screen.getByRole("alert")).toHaveTextContent("second reminder comes after the first");
  expect(request.mock.calls.filter(([path, init]) => path === settingsPath && init?.method === "PATCH")).toHaveLength(0);
});

it("keeps numeric settings read-only when effective authority cannot be read", async () => {
  unavailable = true; show();
  await waitFor(() => expect(screen.getByText("Authority unavailable")).toBeVisible());
  expect(screen.getByLabelText("Pickup note")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Save settings" })).toBeDisabled();
});
