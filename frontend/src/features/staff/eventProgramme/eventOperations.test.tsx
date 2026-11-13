import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { staffRequest } from "../../../lib/api";
import { EventAnalyticsExtras } from "./EventAnalyticsExtras";
import { EventInsightsCard, organizationInsightsPath, spaceInsightsPath } from "./EventInsightsCard";
import { guestFilterKeys, filterQuery } from "./EventStaffLists";
import { parseEmails, SeriesInvitesPanel } from "./SeriesInvitesPanel";
import { windowLabel } from "./AnalyticsColumns";
vi.mock("../../../lib/api", async importOriginal => ({ ...await importOriginal<typeof import("../../../lib/api")>(), staffRequest: vi.fn() }));
const mount = (element: React.ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{element}</QueryClientProvider>);
beforeEach(() => { vi.mocked(staffRequest).mockReset(); });

describe("analytics extras (B24)", () => {
  it("charts sign-ups by day, names the adaptive arrival window and counts written answers", async () => {
    vi.mocked(staffRequest).mockResolvedValue({ event_id: 1, timezone_name: "UTC", window_minutes: 120,
      arrivals: [{ window_start: "2026-11-11T08:00:00Z", count: 4 }], checkin_methods: [], answers: [],
      waitlist: { ever_waitlisted: 0, promoted: 0, still_waiting: 0, conversion_percent: null }, series: [], short_link_visits: null,
      signups: [{ day: "2026-11-01", count: 3 }, { day: "2026-11-02", count: 5 }],
      written_answers: [{ question_id: "q1", label: "What should we change?", type: "long_text", answered: 6 }] });
    mount(<EventAnalyticsExtras makerspaceId={9} eventId={1} />);
    expect(await screen.findByText("Sign-ups over time", { selector: "figcaption" })).toBeInTheDocument();
    expect(screen.getByText(/8 sign-ups over 2 days/)).toBeInTheDocument();
    expect(screen.getByText("Arrivals in 2-hour windows", { selector: "figcaption" })).toBeInTheDocument();
    expect(screen.getByText("6 people wrote an answer")).toBeInTheDocument();
    expect(windowLabel(15)).toBe("15-minute");
  });
});

describe("insights card (A21)", () => {
  it("lists top events and hides the returning share below k", async () => {
    vi.mocked(staffRequest).mockResolvedValue({ window_days: 180, k: 10, top_events: [{ event_id: 3, title: "Repair café", starts_at: "2026-10-01T10:00:00Z", attended: 24 }],
      returning: { suppressed: true, attendees: null, returning_percent: null } });
    const open = vi.fn();
    mount(<EventInsightsCard path={spaceInsightsPath(9)} onOpenEvent={open} />);
    fireEvent.click(await screen.findByRole("button", { name: "Repair café" }));
    expect(open).toHaveBeenCalledWith(3);
    expect(screen.getByText(/Shown once at least 10 people have attended/)).toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/events/insights/?makerspace=9");
    expect(organizationInsightsPath(4)).toBe("/admin/organizations/4/events/insights/");
  });
});

describe("guest list filters (C16, B25)", () => {
  it("offers the reply and per-list filters only with their switches", () => {
    expect(guestFilterKeys([])).toEqual(["status"]);
    expect(guestFilterKeys(["events.attendance_confirmation", "events.checkin_lists"])).toEqual(["status", "reply", "list", "collected"]);
    expect(filterQuery("guests", { reply: "no", list: "4", collected: "yes", q: "ada" })).toBe("reply=no&list=4&collected=yes&q=ada");
  });
});

describe("series invites (B12)", () => {
  it("parses pasted addresses and reports added and skipped", async () => {
    expect(parseEmails("a@x.org, b@x.org\nnot-an-email a@x.org")).toEqual({ valid: ["a@x.org", "b@x.org"], invalid: ["not-an-email"] });
    vi.mocked(staffRequest).mockImplementation(async (_path, options) => options?.method === "POST"
      ? { created: [{ id: 1, expires_at: null, revoked_at: null, created_at: "2026-11-11T10:00:00Z" }], skipped: 1 }
      : { count: 0, next: null, previous: null, results: [] });
    mount(<SeriesInvitesPanel seriesId={5} />);
    fireEvent.change(screen.getByLabelText("Email addresses"), { target: { value: "a@x.org b@x.org" } });
    fireEvent.click(screen.getByRole("button", { name: "Add to the list" }));
    expect(await screen.findByText("1 address added. 1 was already on the list.")).toBeInTheDocument();
    const post = vi.mocked(staffRequest).mock.calls.find(([, options]) => options?.method === "POST")!;
    expect(post[0]).toBe("/admin/event-series/5/invites/");
    expect(JSON.parse(String(post[1]?.body))).toEqual({ emails: ["a@x.org", "b@x.org"] });
  });
  it("removes an entry through the revoke route", async () => {
    vi.mocked(staffRequest).mockResolvedValue({ count: 1, next: null, previous: null, results: [{ id: 8, expires_at: null, revoked_at: null, created_at: "2026-11-11T10:00:00Z" }] });
    mount(<SeriesInvitesPanel seriesId={5} />);
    fireEvent.click(await screen.findByRole("button", { name: "Remove entry 8" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/event-series-invites/8/revoke/", { method: "POST", body: "{}" }));
  });
});
