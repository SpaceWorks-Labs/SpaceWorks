import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { HereNow, MachinesNow } from "./api";
import { isLive, shiftMonth } from "./EventsCalendarSection";
import { HereNowSection } from "./HereNowSection";
import { MachinesNowSection } from "./MachinesNowSection";

const api = vi.hoisted(() => ({ tenantPublicRequest: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), tenantPublicRequest: api.tenantPublicRequest }));

const since = new Date().toISOString();
const here = (overrides: Partial<HereNow> = {}): HereNow => ({ audience: "public", total: 3, others_count: 2, people: [
  { handle: "asha", display_name: "Asha Rao", avatar_url: null, headline: "Welder", status: { preset: "working", note: "Frame" }, skills: ["Welding"], presence_status: "working", since },
], ...overrides });
const wrap = (ui: ReactNode) => <MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider></MemoryRouter>;

beforeEach(() => api.tenantPublicRequest.mockReset());

describe("HereNowSection", () => {
  it("names the visible person as a link and counts everyone else without names", async () => {
    api.tenantPublicRequest.mockResolvedValue(here());
    render(wrap(<HereNowSection slug="lab" enabled />));
    expect(await screen.findByRole("link", { name: /Asha Rao/ })).toHaveAttribute("href", "/asha");
    expect(api.tenantPublicRequest).toHaveBeenCalledWith("lab", "/public/makerspaces/lab/presence/here-now/");
    expect(screen.getByText("+ 2 more here")).toBeInTheDocument();
    expect(screen.getByText("Sign in to see more of who is here.")).toBeInTheDocument();
  });

  it("shows only a count when nobody may be named, and never invents names", async () => {
    api.tenantPublicRequest.mockResolvedValue(here({ people: [], others_count: 7, total: 7 }));
    render(wrap(<HereNowSection slug="lab" enabled />));
    expect(await screen.findByText("7 here now")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "People here now" })).toBeNull();
  });

  it("sends no request and renders nothing while the presence module is off", () => {
    const { container } = render(wrap(<HereNowSection slug="lab" enabled={false} />));
    expect(api.tenantPublicRequest).not.toHaveBeenCalled();
    expect(container).toBeEmptyDOMElement();
  });
});

describe("MachinesNowSection", () => {
  it("shows each machine as a word as well as a colour and never a person", async () => {
    const data: MachinesNow = { in_use: 1, free: 1, out_of_service: 1, items: [
      { name: "Prusa", type: "Printer", status: "in_use" }, { name: "Ender", type: "Printer", status: "free" }, { name: "Laser", type: "Laser", status: "out_of_service" }] };
    api.tenantPublicRequest.mockResolvedValue(data);
    render(wrap(<MachinesNowSection slug="lab" enabled />));
    expect(await screen.findByText("1 free · 1 in use · 1 out of service")).toBeInTheDocument();
    expect(screen.getByText("In use")).toBeInTheDocument();
    expect(screen.getByText("Out of service")).toBeInTheDocument();
  });
});

describe("calendar helpers", () => {
  it("shifts months across a year boundary", () => {
    expect(shiftMonth("2026-12", 1)).toBe("2027-01");
    expect(shiftMonth("2026-01", -1)).toBe("2025-12");
  });
  it("marks an event live only between its start and end", () => {
    const event = { starts_at: "2026-11-11T10:00:00Z", ends_at: "2026-11-11T12:00:00Z" };
    expect(isLive(event, Date.parse("2026-11-11T11:00:00Z"))).toBe(true);
    expect(isLive(event, Date.parse("2026-11-11T12:00:01Z"))).toBe(false);
  });
});
