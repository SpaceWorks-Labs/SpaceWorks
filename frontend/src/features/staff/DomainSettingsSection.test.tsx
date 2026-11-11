import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { staffRequest } from "../../lib/api";
import { FEATURE_DEFINITIONS } from "../../lib/features";
import { DomainSettingsSection } from "./DomainSettingsSection";
import type { DomainSettings } from "./domainSettingsApi";

vi.mock("../../lib/api", () => ({ staffRequest: vi.fn() }));

const events: DomainSettings = {
  domain: "events",
  editable: true,
  features: [
    { key: "events.website", label: "Event websites", description: "", parent_module: "events",
      requires_features: [], enabled: false, available: true, editable: true, locked: false },
    { key: "events.embed", label: "Event embeds", description: "", parent_module: "events",
      requires_features: ["events.website"], enabled: false, available: false, editable: true, locked: false },
  ],
  settings: { event_default_registration_audience: "members", event_reminder_lead_hours: [24] },
  setting_permissions: {
    event_default_registration_audience: { editable: true, locked: false },
    event_reminder_lead_hours: { editable: true, locked: false },
  },
};
const readOnly: DomainSettings = {
  ...events, editable: false,
  features: events.features.map(feature => ({ ...feature, editable: false })),
  setting_permissions: {
    event_default_registration_audience: { editable: false, locked: false },
    event_reminder_lead_hours: { editable: false, locked: true },
  },
};
const path = "/admin/makerspace/7/domain-settings/events";

beforeEach(() => { vi.mocked(staffRequest).mockReset(); });

function mount(data: DomainSettings = events, spaceManager = false) {
  vi.mocked(staffRequest).mockImplementation(async (url: string) => (url.endsWith("/settings-authority/effective")
    ? { modules: [{ module: "events", space_manager: spaceManager, grant_id: null, keys: [] }] }
    : url.endsWith("/settings-authority/locks") ? [] : data) as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(<QueryClientProvider client={client}><DomainSettingsSection makerspaceId={7} domain="events" /></QueryClientProvider>);
  return invalidate;
}

it("toggles only the clicked domain key and refreshes the console's makerspace and staff caches", async () => {
  const invalidate = mount();
  const toggle = await screen.findByRole("checkbox", { name: /^Event websites/ });
  fireEvent.click(toggle);
  await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(path, {
    method: "PATCH", body: JSON.stringify({ features: { "events.website": true } }),
  }));
  await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["staff", "me"] }));
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["makerspace-settings", 7] });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["staff", "makerspaces"] });
});

it("disables a switch whose module is missing and explains why", async () => {
  mount();
  const embed = await screen.findByRole("checkbox", { name: /^Event embeds/ });
  expect(embed).toBeDisabled();
  expect(screen.getByText("Needs a module that is not installed here.")).toBeInTheDocument();
});

it("saves only changed settings, parsed back to the API's types", async () => {
  mount();
  const hours = await screen.findByRole("textbox", { name: "Event reminder lead hours" });
  fireEvent.change(hours, { target: { value: "48, 2" } });
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(path, {
    method: "PATCH", body: JSON.stringify({ settings: { event_reminder_lead_hours: [48, 2] } }),
  }));
});

it("refuses malformed lead hours before calling the server", async () => {
  mount();
  fireEvent.change(await screen.findByRole("textbox", { name: "Event reminder lead hours" }), { target: { value: "48, 48" } });
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/unique whole hours/);
  expect(vi.mocked(staffRequest).mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(0);
});

it("locks every control when the server says this actor cannot write", async () => {
  mount(readOnly);
  expect(await screen.findByRole("note")).toHaveTextContent(/Space Manager/);
  expect(screen.getByRole("checkbox", { name: /^Event websites/ })).toBeDisabled();
  expect(screen.getByRole("combobox", { name: "Default registration audience" })).toBeDisabled();
});

it("mirrors the event and booking website, embed and integration switches", () => {
  const keys = new Map(FEATURE_DEFINITIONS.map((feature) => [feature.key, feature]));
  for (const [key, parent] of [["events.website", "events"], ["events.embed", "events"], ["events.api_read", "events"],
    ["bookings.website", "bookings"], ["bookings.embed", "bookings"], ["bookings.api_read", "bookings"]]) {
    expect(keys.get(key)?.parent_module).toBe(parent);
  }
  expect(keys.get("events.embed")?.label).toBe("Event embeds");
});

it("shows a manager which settings the Space Manager locked, without a lock control", async () => {
  mount(readOnly);
  expect(await screen.findByText("Locked by the Space Manager")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /for managers$/ })).not.toBeInTheDocument();
});

it("lets the Space Manager lock a switch for managers", async () => {
  mount(events, true);
  const lock = await screen.findByRole("button", { name: "Lock for managers Event websites" });
  expect(lock).toHaveTextContent("Lock for managers");
  expect(lock).toHaveAttribute("aria-pressed", "false");
  fireEvent.click(lock);
  await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/settings-authority/locks", {
    method: "PUT", body: JSON.stringify({ setting_key: "events.website", locked: true }),
  }));
});
