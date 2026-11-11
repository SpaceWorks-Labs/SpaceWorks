import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MyBookings, type MemberBooking } from "./MyBookings";

const { memberRequest, getAccessToken } = vi.hoisted(() => ({ memberRequest: vi.fn(), getAccessToken: vi.fn((): string | null => null) }));
vi.mock("../../lib/api", () => ({ memberRequest, getAccessToken }));

const booking: MemberBooking = {
  public_token: "my-token", space_name: "Laser room", timezone: "Asia/Kolkata",
  starts_at: "2030-01-15T10:00:00Z", ends_at: "2030-01-15T11:00:00Z",
  status: "confirmed", cancellation_cutoff_at: "2030-01-14T10:00:00Z", can_cancel: true,
};

function show(initialPeriod: "upcoming" | "past" = "upcoming") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(<QueryClientProvider client={client}><MyBookings slug="lab" initialPeriod={initialPeriod} /></QueryClientProvider>);
  return invalidate;
}

beforeEach(() => { memberRequest.mockReset(); getAccessToken.mockReturnValue(null); });

describe("my bookings", () => {
  it("uses local time, confirms cancellation and refreshes member history and availability", async () => {
    memberRequest.mockImplementation((_path: string, options?: { method?: string }) => options?.method === "POST"
      ? Promise.resolve({ ...booking, status: "cancelled", can_cancel: false })
      : Promise.resolve({ count: 1, next: null, previous: null, results: [booking] }));
    const invalidate = show();
    expect(await screen.findByText("Laser room")).toBeVisible();
    expect(within(screen.getByRole("tabpanel", { name: "Upcoming" })).getByText("Laser room")).toBeVisible();
    expect(screen.getByRole("tab", { name: "Upcoming" })).toHaveAttribute("aria-controls", screen.getByRole("tabpanel").id);
    expect(screen.getByText(/Asia\/Kolkata/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Booking actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Cancel booking" }));
    expect(memberRequest).not.toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ method: "POST" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm cancellation" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith(
      "/public/lab/my-bookings/my-token/cancel/", { method: "POST", body: "{}" },
    ));
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["member", "lab"] }));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["public-space-availability", "lab"] });
    expect(screen.queryByRole("button", { name: "Confirm cancellation" })).toBeNull();
  });

  it("loads past and subsequent pages, and never offers cancellation after the cutoff", async () => {
    memberRequest.mockResolvedValue({ count: 25, next: "next", previous: null, results: [{ ...booking, can_cancel: false }] });
    show();
    await screen.findByText("Laser room");
    expect(screen.queryByRole("button", { name: "Cancel booking" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/public/lab/my-bookings/?period=upcoming&page=2"));
    fireEvent.click(screen.getByRole("tab", { name: "Past" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/public/lab/my-bookings/?period=past&page=1"));
  });

  it("shows a rejected cancellation and keeps the confirmation available for retry", async () => {
    memberRequest.mockImplementation((_path: string, options?: { method?: string }) => options?.method === "POST"
      ? Promise.reject(new Error("The cancellation cutoff has passed."))
      : Promise.resolve({ count: 1, next: null, previous: null, results: [booking] }));
    const invalidate = show();
    await screen.findByText("Laser room");
    fireEvent.click(screen.getByRole("button", { name: "Booking actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Cancel booking" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm cancellation" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The cancellation cutoff has passed.");
    expect(screen.getByRole("button", { name: "Confirm cancellation" })).toBeEnabled();
    expect(invalidate).not.toHaveBeenCalled();
  });

  it("clears the previous owner's cached bookings and open editor when accounts change", async () => {
    let owner = 1;
    getAccessToken.mockImplementation(() => `header.${btoa(JSON.stringify({ user_id: owner }))}.signature`);
    memberRequest.mockImplementation((path: string) => Promise.resolve(path.includes("calendar/")
      ? { enabled: false }
      : { count: 1, next: null, previous: null, results: [{ ...booking, space_name: owner === 1 ? "First owner's room" : "Second owner's room" }] }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const tree = <QueryClientProvider client={client}><MyBookings slug="lab" /></QueryClientProvider>;
    const { rerender, unmount } = render(tree);
    try {
      await screen.findByText("First owner's room");
      fireEvent.click(screen.getByRole("button", { name: "Reschedule booking" }));
      expect(screen.getByRole("form", { name: "Reschedule booking" })).toBeVisible();
      owner = 2;
      rerender(<QueryClientProvider client={client}><MyBookings slug="lab" /></QueryClientProvider>);
      await screen.findByText("Second owner's room");
      expect(screen.queryByText("First owner's room")).toBeNull();
      expect(screen.queryByRole("form", { name: "Reschedule booking" })).toBeNull();
    } finally { unmount(); client.clear(); }
  });
});


it("opens the actual past-booking query from the account history shortcut", async () => {
  memberRequest.mockImplementation((path: string) => Promise.resolve(path.includes("calendar/") ? { enabled: false }
    : { count: 1, next: null, previous: null, results: [{ ...booking, status: "cancelled", can_cancel: false }] }));
  show("past");
  expect(await screen.findByText("Laser room")).toBeVisible();
  expect(screen.getByRole("tab", { name: "Past" })).toHaveAttribute("aria-selected", "true");
  expect(memberRequest).toHaveBeenCalledWith("/public/lab/my-bookings/?period=past&page=1");
});

describe("report a problem on a booking (decision 220(d)1)", () => {
  const machineTime = { ...booking, public_token: "machine-token", space_name: "Laser A time", machine_time: true };
  const room = { ...booking, public_token: "room-token", space_name: "Wood shop", machine_time: false };
  const showWith = (props: { canReport?: boolean; canReportMachines?: boolean }) => {
    memberRequest.mockResolvedValue({ count: 2, next: null, previous: null, results: [machineTime, room] });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MyBookings slug="lab" {...props} /></QueryClientProvider>);
  };
  const reportButtons = () => screen.queryAllByRole("button", { name: "Report a problem" });

  it("machine reporting alone offers the button on machine-time bookings only", async () => {
    showWith({ canReportMachines: true });
    await screen.findByText("Laser A time");
    expect(reportButtons()).toHaveLength(1);
  });

  it("room reporting alone keeps both (the server files machine time on the room then)", async () => {
    showWith({ canReport: true });
    await screen.findByText("Wood shop");
    expect(reportButtons()).toHaveLength(2);
  });

  it("neither switch shows no button", async () => {
    showWith({});
    await screen.findByText("Wood shop");
    expect(reportButtons()).toHaveLength(0);
  });
});
