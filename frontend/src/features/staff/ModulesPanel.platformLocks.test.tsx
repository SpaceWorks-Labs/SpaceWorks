import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ModulesPanel } from "./ModulesPanel";

// Module audit 0.12.0: a switch the platform decides is shown LOCKED, with the reason, in the space's
// Areas & add-ons screen. Behaviour only (roles, names, disabled state, reason wording by meaning), so
// the assertions survive a visual redesign of the cards.
const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual("../../lib/api"), staffRequest: request }));

const row = (key: string, label: string, extra: Record<string, unknown> = {}) => ({
  key, label, description: `${label} area.`, installed: false, core: false, available: true,
  requires: [], pulls_in: [], required_by: [], workflows: [], install_requires_superadmin: false, limits: [],
  lock_reason: null, ...extra,
});
const data = {
  groups: [{
    key: "inventory", label: "Inventory", description: "Always on.", always_on: true, installed_count: 1, module_count: 1,
    modules: [row("scanner", "Scanner", { installed: true, core: true, lock_reason: "core" })],
  }, {
    key: "events", label: "Events", description: "Events.", always_on: false, installed_count: 0, module_count: 1,
    modules: [row("events", "Events", { install_requires_superadmin: true, limits: ["events"], lock_reason: "limit" })],
  }, {
    key: "shop", label: "Shop", description: "Shop.", always_on: false, installed_count: 0, module_count: 1,
    modules: [row("shop", "Shop", { available: false, lock_reason: "not_shipped" })],
  }, {
    key: "bookings", label: "Bookings", description: "Bookings.", always_on: false, installed_count: 0, module_count: 1,
    modules: [row("bookings", "Bookings", { installed: true })],
  }],
  deployment: null,
  // Decision 329 (c): a feature whose own app is not shipped, under an installed module.
  feature_locks: { "bookings.recurring": "not_shipped" },
};

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ModulesPanel makerspaceId={7} /></QueryClientProvider>);
}

beforeEach(() => {
  request.mockReset();
  request.mockImplementation(async (path: string, init?: { method?: string }) => init?.method ? {} : path.endsWith("/modules")
    ? data : path.endsWith("/roles") ? [] : { id: 7, enabled_modules: ["scanner", "bookings"], enabled_features: ["bookings.recurring"] });
});

/** Whether the screen offers a switch for this module that can actually be flipped. */
function offersEnabledSwitch(name: string) {
  return screen.queryAllByRole("switch", { name }).some(element => element.getAttribute("aria-label") === name
    && !(element as HTMLInputElement).disabled);
}

describe("platform-locked module switches", () => {
  it("shows a module this deployment does not ship as locked, with the reason", async () => {
    show();
    await screen.findByRole("switch", { name: "Bookings" });
    expect(offersEnabledSwitch("Shop")).toBe(false);
    expect(screen.getByText(/not (installed on this server|shipped)/i)).toBeVisible();
  });

  it("shows a limit-gated module as locked for the Space Manager, naming the platform administrator", async () => {
    show();
    await screen.findByRole("switch", { name: "Bookings" });
    expect(offersEnabledSwitch("Events")).toBe(false);
    expect(screen.getByText(/usage limit/i)).toHaveTextContent(/platform administrator/i);
  });

  it("shows a core module as always on and never offers to switch it off", async () => {
    show();
    await screen.findByRole("switch", { name: "Bookings" });
    expect(offersEnabledSwitch("Scanner")).toBe(false);
    expect(screen.getAllByText(/always on/i).length).toBeGreaterThan(0);
  });

  it("leaves an unlocked module switchable", async () => {
    show();
    const bookings = await screen.findByRole("switch", { name: "Bookings" });
    expect(bookings).toBeEnabled();
  });
});

describe("platform-locked feature switches (decision 329 c)", () => {
  it("shows a feature whose app is not shipped as locked with the reason, and its siblings stay switchable", async () => {
    show();
    await screen.findByRole("switch", { name: "Bookings" });
    const toggle = screen.getAllByRole("button").find(button => /features/i.test(button.textContent ?? "")
      && button.closest("article")?.querySelector("h3")?.textContent === "Bookings");
    expect(toggle).toBeDefined();
    fireEvent.click(toggle!);
    const list = await screen.findByRole("list", { name: /Bookings/ });
    const locked = within(list).getByRole("switch", { name: "Recurring bookings" });
    expect(locked).toBeDisabled();
    expect(locked).not.toBeChecked();
    expect(within(list).getByText(/not installed on this server/i)).toBeVisible();
    const others = within(list).getAllByRole("switch").filter(element => element !== locked);
    expect(others.length).toBeGreaterThan(0);
    expect(others.some(element => !(element as HTMLInputElement).disabled)).toBe(true);
  });
});
