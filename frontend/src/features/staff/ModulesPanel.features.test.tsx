// Ported from the former MakerspaceFeatureSettings.test.tsx (HEAD), whose feature switches moved to the
// Areas & add-ons screen (ModulesPanel / ModuleFeatureRows). Same intent and assertions, adapted:
//  1. enable a feature while preserving the others and refreshing settings (PATCH the full list);
//  2. a feature is gated on its parent module (the old disabled checkbox is now a confirm that offers the parent);
//  3. one plain line explains each switch and raw module keys never show (decision 235).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ModulesPanel } from "./ModulesPanel";
import { clearToasts } from "../../components/ui/toastStore";
import { row } from "./modules/test/moduleFixtures";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual("../../lib/api"), staffRequest: request }));

const feature = "events.organization_audience";
const name = "Participating organizations audience";
const modules = (eventsOn: boolean) => ({ deployment: null, profiles: [], groups: [
  { key: "inventory", label: "Inventory", description: "Spine.", always_on: true, installed_count: 1, module_count: 1,
    modules: [row("public_inventory", "Public inventory", { installed: true, core: true, lock_reason: "core" })] },
  { key: "events", label: "Events", description: "Event scheduling.", always_on: false, installed_count: eventsOn ? 1 : 0, module_count: 1,
    modules: [row("events", "Events", { installed: eventsOn })] }] });

function mount(eventsOn = true) {
  request.mockReset(); clearToasts();
  request.mockImplementation(async (path = "", init?: { method?: string }) => {
    if (init?.method) return {};
    if (path.endsWith("/modules")) return modules(eventsOn);
    if (path.endsWith("/roles")) return [];
    return { id: 7, enabled_modules: eventsOn ? ["events"] : [], enabled_features: ["events.invites"] };
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(<QueryClientProvider client={client}><ModulesPanel makerspaceId={7} /></QueryClientProvider>);
  return invalidate;
}
async function openEvents() {
  const card = (await screen.findByRole("heading", { level: 3, name: "Events" })).closest("article")!;
  fireEvent.click(within(card).getByRole("button", { name: /^Features:/ }));
  return card;
}
beforeEach(() => request.mockReset());

it("lets staff enable organization audiences while preserving other features and refreshing settings", async () => {
  const invalidate = mount();
  const card = await openEvents();
  const toggle = within(card).getByRole("switch", { name });
  expect(toggle).toBeEnabled();
  expect(toggle).not.toBeChecked();
  fireEvent.click(toggle);
  await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/makerspaces/7", {
    method: "PATCH", body: JSON.stringify({ enabled_features: ["events.invites", feature] }),
  }));
  await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["makerspace-settings", 7] }));
});

it("gates the organization-audience toggle on the events module", async () => {
  mount(false);
  const card = await openEvents();
  const toggle = within(card).getByRole("switch", { name });
  expect(toggle).not.toBeChecked();
  expect(within(card).getAllByText(/Needs Events/).length).toBeGreaterThan(0);
  fireEvent.click(toggle);
  // It does not write on its own: it asks to switch Events on too.
  expect(await screen.findByRole("dialog")).toBeVisible();
  expect(request.mock.calls.filter(([, init]) => init?.method)).toEqual([]);
});

it("explains each switch in one plain line and never shows raw module keys (decision 235)", async () => {
  mount();
  const card = await openEvents();
  const toggle = within(card).getByRole("switch", { name });
  expect(toggle).toHaveAccessibleDescription("Limit registration to members of the organising organisation.");
  expect(screen.getAllByText("Public inventory").length).toBeGreaterThan(0);
  expect(screen.queryByText("public_inventory")).not.toBeInTheDocument();
});
