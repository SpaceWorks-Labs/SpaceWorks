import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { notifySessionCleared } from "../../../lib/api/sessionContext";
import { MemberCalendarLinks } from "./MemberCalendarLinks";

const { memberRequest } = vi.hoisted(() => ({ memberRequest: vi.fn() }));
// A real bootstrap always names its space; the panel's Help link (17930bb7) reads it.
const tenant: { mode: "single"; bootstrap: { makerspace: { slug: string }; features: string[]; modules: string[] } } = {
  mode: "single", bootstrap: { makerspace: { slug: "lab" }, features: [], modules: ["events", "bookings"] },
};
vi.mock("../../../lib/api", async () => ({
  ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"), memberRequest,
}));
const session = vi.hoisted(() => ({ owner: "1" }));
vi.mock("../../inventory/useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: session.owner }) }));
vi.mock("../../../lib/api/sessionTokens", async (original) => ({
  ...await original<typeof import("../../../lib/api/sessionTokens")>(), getSessionOwner: () => session.owner }));
vi.mock("../../../lib/tenant", async (original) => ({ ...await original<typeof import("../../../lib/tenant")>(),
  useOptionalTenant: () => tenant }));

function show(features: string[]) {
  tenant.bootstrap.features = features;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemberCalendarLinks makerspaceId={5} makerspaceSlug="lab" /></QueryClientProvider>);
}

beforeEach(() => {
  session.owner = "1";
  memberRequest.mockReset();
  memberRequest.mockImplementation((_path: string, init?: RequestInit) => Promise.resolve(init?.method === "POST"
    ? { feed_url: "https://api.example/api/v1/public/lab/calendar/shifts/secret-token.ics", token_hint: "en.ics" }
    : { enabled: false, token_hint: null }));
});

describe("MemberCalendarLinks", () => {
  it("shows each link only while its switch is on", () => {
    show(["events.shifts_feed"]);
    expect(screen.getByText("My shifts calendar")).toBeInTheDocument();
    expect(screen.queryByText("Everything in one calendar")).not.toBeInTheDocument();
    expect(screen.queryByText("My bookings calendar")).not.toBeInTheDocument();
    expect(screen.queryByText("My event calendar")).not.toBeInTheDocument();
    expect(screen.queryByText("Public events calendar")).not.toBeInTheDocument();
  });

  it("lists the public events calendar and the combined link when on", () => {
    show(["calendar.combined_feed", "events.public_feed"]);
    expect(screen.getByText("Everything in one calendar")).toBeInTheDocument();
    expect((screen.getByRole("textbox", { name: "Public events calendar link" }) as HTMLInputElement).value)
      .toContain("/public/lab/events-calendar.ics");
  });

  it("reveals a new private link once, after the person confirms the bearer risk", async () => {
    show(["events.shifts_feed"]);
    const create = await screen.findByRole("button", { name: "Create link" });
    await waitFor(() => expect(create).toBeEnabled());
    fireEvent.click(create);
    fireEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    expect(memberRequest).not.toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ method: "POST" }));
    fireEvent.click(create);
    fireEvent.click(await screen.findByRole("button", { name: "Yes, create link" }));
    const revealed = await screen.findByRole("textbox", { name: "My shifts calendar subscription link" });
    expect(revealed).toHaveValue("https://api.example/api/v1/public/lab/calendar/shifts/secret-token.ics");
    expect(memberRequest).toHaveBeenCalledWith("/member/makerspaces/5/calendar-feeds/shifts/", expect.objectContaining({ method: "POST" }));
  });

  it("drops a private link that arrives after the account switched away and back", async () => {
    let finish!: (value: { feed_url: string; token_hint: string }) => void;
    memberRequest.mockImplementation((_path: string, init?: RequestInit) => init?.method === "POST"
      ? new Promise(resolve => { finish = resolve; }) : Promise.resolve({ enabled: false, token_hint: null }));
    show(["events.shifts_feed"]);
    const create = await screen.findByRole("button", { name: "Create link" });
    await waitFor(() => expect(create).toBeEnabled());
    fireEvent.click(create);
    fireEvent.click(await screen.findByRole("button", { name: "Yes, create link" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ method: "POST" })));
    act(() => { session.owner = "2"; notifySessionCleared("person"); session.owner = "1"; notifySessionCleared("person"); });
    await act(async () => finish({ feed_url: "https://api.example/old-owner.ics", token_hint: "er.ics" }));
    expect(screen.queryByRole("textbox", { name: "My shifts calendar subscription link" })).toBeNull();
  });

  it("hides private links while no account owns the session, but keeps the public calendar", () => {
    session.owner = "";
    show(["events.shifts_feed", "events.public_feed"]);
    expect(screen.queryByText("My shifts calendar")).toBeNull();
    expect(screen.getByText("Public events calendar")).toBeInTheDocument();
  });
});
