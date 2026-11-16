import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PublicStatsSettingsResponse } from "./api";

const mocks = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"),
  staffRequest: mocks.staffRequest }));

import { PublicStatsSettingsPanel } from "./PublicStatsSettingsPanel";

function response(overrides: Partial<PublicStatsSettingsResponse> = {}): PublicStatsSettingsResponse {
  return {
    settings: { enabled: true, sections: ["machines", "printing", "lending"], period: "month", headline: [],
      tv_mode_enabled: false, tv_refresh_seconds: 60 },
    can_edit: true,
    choices: {
      sections: [{ key: "events", label: "Events" }, { key: "machines", label: "Machines" }, { key: "printing", label: "Printing" },
        { key: "lending", label: "Inventory" }, { key: "community", label: "Community" }],
      periods: [{ key: "month", label: "This month" }, { key: "year", label: "This year" }, { key: "all", label: "All time" },
        { key: "fy", label: "This financial year" }],
      metrics: [
        { key: "events.upcoming", section: "events", label: "Upcoming events" }, { key: "events.held", section: "events", label: "Events held" },
        { key: "machines.hours", section: "machines", label: "Machine hours" }, { key: "lending.loans", section: "lending", label: "Loans" },
        { key: "community.bookings", section: "community", label: "Bookings" },
      ],
      max_headline: 4, tv_refresh_min: 30, tv_refresh_max: 3600,
    },
    ...overrides,
  };
}

function show(area?: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><PublicStatsSettingsPanel makerspaceId={7} slug="lab" area={area} /></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  mocks.staffRequest.mockReset();
  mocks.staffRequest.mockImplementation((_path: string, init?: RequestInit) =>
    Promise.resolve(init?.method === "PATCH" ? { ...response(), settings: { ...response().settings, ...JSON.parse(String(init.body)) } } : response()));
});

describe("Settings › Public stats (#170)", () => {
  function granular() {
    const data = response({ can_edit: false });
    data.choices.widgets = [
      { key: "lending.tools_out", section: "lending", owner_module: "inventory", label: "Tools currently out", kind: "list" },
      { key: "events.held", section: "events", owner_module: "events", label: "Held event count", kind: "count" },
      { key: "lending.current_loans", section: "lending", owner_module: "inventory", label: "Borrower list", kind: "list" },
      { key: "printing.queue", section: "printing", owner_module: "machines", label: "Printer queue", kind: "list" },
    ];
    data.capabilities = { settings: {}, visibility: {
      "lending.tools_out": { editable: true, locked: false, available: true },
      "events.held": { editable: false, locked: false, available: true },
      "lending.current_loans": { editable: false, locked: true, available: true },
      "printing.queue": { editable: true, locked: false, available: false },
    } };
    return data;
  }

  it("lets an Inventory Manager change only their area without sending global settings", async () => {
    const data = granular();
    mocks.staffRequest.mockImplementation((_path: string, init?: RequestInit) => Promise.resolve(init?.method === "PATCH"
      ? { ...data, settings: { ...data.settings, ...JSON.parse(String(init.body)) } } : data));
    show("inventory");
    const control = await screen.findByRole("checkbox", { name: "Tools currently out" });
    expect(screen.queryByRole("checkbox", { name: "Publish public stats" })).toBeNull();
    expect(screen.queryByRole("checkbox", { name: "Held event count" })).toBeNull();
    expect(screen.getByRole("checkbox", { name: "Borrower list" })).toBeDisabled();
    expect(screen.queryByRole("checkbox", { name: "Printer queue" })).toBeNull();
    expect(screen.getByRole("button", { name: "Save public stats" })).toBeDisabled();
    fireEvent.click(control);
    fireEvent.click(screen.getByRole("button", { name: "Save public stats" }));
    await waitFor(() => expect(mocks.staffRequest).toHaveBeenCalledTimes(2));
    expect(JSON.parse(String(mocks.staffRequest.mock.calls[1][1].body))).toEqual({ visibility: { "lending.tools_out": false } });
  });

  it("honours effective Space Manager overrides while retaining the lock explanation", async () => {
    const data = granular();
    data.can_edit = true;
    data.capabilities!.visibility["lending.current_loans"].editable = true;
    mocks.staffRequest.mockResolvedValue(data);
    show();
    expect(await screen.findByRole("checkbox", { name: "Borrower list" })).toBeEnabled();
    expect(screen.getByText("Locked for delegated managers. You can override this lock.")).toBeVisible();
    expect(screen.getByRole("checkbox", { name: "Held event count" })).toBeDisabled();
    expect(screen.queryByRole("checkbox", { name: "Printer queue" })).toBeNull();
  });

  it("reorders and toggles sections, then saves only changed page settings", async () => {
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Move Inventory up" }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Community/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Printing/ }));
    fireEvent.change(screen.getByRole("combobox", { name: "Stats period" }), { target: { value: "fy" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "Turn on TV mode" }));
    fireEvent.click(screen.getByRole("button", { name: "Save public stats" }));
    await waitFor(() => expect(mocks.staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/public-stats-settings",
      expect.objectContaining({ method: "PATCH" })));
    const body = JSON.parse(String(mocks.staffRequest.mock.calls.at(-1)?.[1]?.body));
    expect(body).toEqual({ sections: ["machines", "lending", "community"], period: "fy", tv_mode_enabled: true });
  });

  it("caps the headline at the maximum, in tick order", async () => {
    show();
    for (const name of ["Machine hours", "Events held", "Loans", "Bookings"]) fireEvent.click(await screen.findByRole("checkbox", { name: new RegExp(`^${name}`) }));
    expect(screen.getByRole("checkbox", { name: /^Upcoming events/ })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Save public stats" }));
    await waitFor(() => expect(mocks.staffRequest).toHaveBeenCalledTimes(2));
    expect(JSON.parse(String(mocks.staffRequest.mock.calls[1][1].body)).headline).toEqual(
      ["machines.hours", "events.held", "lending.loans", "community.bookings"]);
  });

  it("is read-only for anyone but the Space Manager and links the previews", async () => {
    mocks.staffRequest.mockResolvedValue(response({ can_edit: false }));
    show();
    expect(await screen.findByText("These public stats settings are read-only for your account.")).toBeVisible();
    expect(screen.getByRole("checkbox", { name: "Publish public stats" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save public stats" })).toBeNull();
    expect(screen.getByRole("link", { name: /Preview TV mode/ })).toHaveAttribute("href", "/m/lab/stats/tv");
  });
});
