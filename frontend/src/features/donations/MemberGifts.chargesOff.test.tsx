import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { MemberGifts } from "./MemberGifts";

const state = vi.hoisted(() => ({ features: ["finance.donations"] as string[] }));
vi.mock("../members/calendarFeeds/MemberCalendarLinks", () => ({
  useSpaceSwitches: () => Object.assign((key: string) => state.features.includes(key), { known: true }) }));
vi.mock("../../lib/tenant", async original => ({ ...(await original<typeof import("../../lib/tenant")>()),
  useTenantPath: () => (path: string) => `/m/lab/${path}` }));
vi.mock("./donationsApi", async original => ({ ...(await original<typeof import("./donationsApi")>()),
  donationsApi: { memberGifts: vi.fn(async () => []), memberPledges: vi.fn(async () => []), changeMemberPledge: vi.fn() } }));

function show() {
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><MemberGifts makerspaceId={3} makerspaceSlug="lab" /></MemoryRouter></QueryClientProvider>);
}

describe("My gifts (#184)", () => {
  it("offers no new gift while donation charges are off", () => {
    state.features = ["finance.donations", "charges.enabled"];
    show();
    expect(screen.getByRole("heading", { name: "My gifts" })).toBeVisible();
    expect(screen.queryByRole("link", { name: "Give again" })).toBeNull();
  });

  it("offers it when donations are tracked", () => {
    state.features = ["finance.donations", "charges.enabled", "charges.donations"];
    show();
    expect(screen.getByRole("link", { name: "Give again" })).toBeVisible();
  });
});
