import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardPanel } from "./DashboardPanel";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest }));

const makerspace = { id: 7, name: "Forge", public_code: "forge", slug: "forge", telegram_group_chat_id: "",
  frontend_domain: null, hidden_from_central_directory: false };

function renderPanel(extra: Record<string, unknown> = {}, allowedTabs = ["events", "bookings"]) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter>
    <DashboardPanel makerspace={{ ...makerspace, enabled_modules: ["staff_admin", "events", "bookings"], ...extra }}
      canManageMakerspace={false} allowedTabs={allowedTabs} />
  </MemoryRouter></QueryClientProvider>);
}

async function revealStats() {
  await waitFor(() => expect(screen.queryByRole("status", { name: "Loading content" })).not.toBeInTheDocument());
  const disclosure = screen.queryByRole("button", { name: "Everything else" });
  if (disclosure) fireEvent.click(disclosure);
}

beforeEach(() => { staffRequest.mockReset(); });

describe("dashboard today tiles (open item A24)", () => {
  it("shows today's events, check-ins and bookings when the server sends them", async () => {
    staffRequest.mockResolvedValue({ scope_mode: "full", today_events: 2, today_check_ins: 15, today_bookings: 3, failed_areas: [] });
    renderPanel();
    await revealStats();
    expect(screen.getByRole("link", { name: /Events today 2/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Checked in today 15/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Bookings today 3/ })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("hides the tiles the server did not send and those outside the viewer's tabs", async () => {
    staffRequest.mockResolvedValue({ scope_mode: "full", today_events: 2 });
    renderPanel({}, ["events"]);
    await revealStats();
    expect(screen.getByRole("link", { name: /Events today 2/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Bookings today/ })).toBeNull();
  });

  it("shows room outages only while room maintenance is on", async () => {
    staffRequest.mockResolvedValue({ scope_mode: "full", room_outages_week: 1 });
    renderPanel({ enabled_features: ["bookings.room_maintenance"] });
    await revealStats();
    expect(screen.getByRole("link", { name: /Rooms out of service this week 1/ })).toBeInTheDocument();
  });
});

describe("dashboard partial failures (open item A31)", () => {
  it("names the areas that could not load and retries", async () => {
    staffRequest.mockResolvedValue({ scope_mode: "full", failed_areas: ["events", "inventory"] });
    renderPanel();
    expect(await screen.findByText(/Couldn't load some numbers: Events, Inventory/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledTimes(2));
  });
});
