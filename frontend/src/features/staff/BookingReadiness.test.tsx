import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import { ExistingBookingReadiness, StaffBookingReadiness } from "./BookingReadiness";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => api);
vi.mock("../../lib/api/sessionContext", () => ({ consoleSessionHref: (path: string) => path }));

beforeEach(() => { vi.resetAllMocks(); });

const repair = { ready: false, maintenance_link: { machine_id: 12 }, checks: [
  { code: "room_outage", state: "ok", detail: "" },
  { code: "machine_repair", state: "blocked", detail: "" },
  { code: "machine_lockout", state: "warning", detail: "" },
] };

function form(props: Partial<{ memberId: string; start: string; end: string }> = {}, path = "/m/lab/admin/bookings") {
  return render(<MemoryRouter initialEntries={[path]}>
    <StaffBookingReadiness spaceId={4} memberId={props.memberId ?? "8"} start={props.start ?? "2026-12-01T10:00"} end={props.end ?? "2026-12-01T11:00"} />
  </MemoryRouter>);
}

it("asks the server for the chosen room, window and member and shows repair, lockout and the maintenance link", async () => {
  api.staffRequest.mockResolvedValue(repair);
  form();
  expect(await screen.findByText("The machine is under repair at that time.")).toBeInTheDocument();
  expect(screen.getByText(/Overdue safety maintenance locks the machine/)).toBeInTheDocument();
  expect(screen.getByText("No room outage.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open machine maintenance record" }))
    .toHaveAttribute("href", "/m/lab/admin/machines?machine=12&detail_tab=Maintenance");
  const [path] = api.staffRequest.mock.calls[0];
  const url = new URL(path, "http://x");
  expect(url.pathname).toBe("/admin/spaces/4/bookings/readiness/");
  expect(url.searchParams.get("member_id")).toBe("8");
  expect(url.searchParams.get("starts_at")).toBe(new Date("2026-12-01T10:00").toISOString());
  expect(url.searchParams.get("ends_at")).toBe(new Date("2026-12-01T11:00").toISOString());
});

it("hides the link when the server withholds it (module off or no machine scope)", async () => {
  api.staffRequest.mockResolvedValue({ ...repair, maintenance_link: null });
  form({}, "/admin/bookings");
  expect(await screen.findByText("The machine is under repair at that time.")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Open machine maintenance record" })).toBeNull();
});

it("names missing machine access and omits member_id until a member is chosen", async () => {
  api.staffRequest.mockResolvedValue({ ready: false, maintenance_link: null, checks: [
    { code: "machine_access", state: "blocked", detail: "", reason: "no_machine_access" }] });
  form({ memberId: "" });
  expect(await screen.findByText("The member has not been given access to this machine.")).toBeInTheDocument();
  expect(new URL(api.staffRequest.mock.calls[0][0], "http://x").searchParams.has("member_id")).toBe(false);
});

it("sends nothing until the window is complete and ordered", () => {
  form({ end: "" });
  form({ start: "2026-12-01T11:00", end: "2026-12-01T10:00" });
  expect(api.staffRequest).not.toHaveBeenCalled();
});

it("stays silent when the readiness view is unavailable, since submit re-checks", async () => {
  api.staffRequest.mockRejectedValue(new Error("403"));
  form();
  await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
  expect(screen.queryByRole("region", { name: "Booking readiness" })).toBeNull();
});

it("reads an existing booking's readiness from its own route, only once opened", async () => {
  api.staffRequest.mockResolvedValue(repair);
  render(<MemoryRouter initialEntries={["/admin/bookings"]}><ExistingBookingReadiness bookingId={31} /></MemoryRouter>);
  // One panel per row of the bookings list: nothing is fetched until staff ask.
  const toggle = screen.getByRole("button", { name: "Check readiness" });
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect(api.staffRequest).not.toHaveBeenCalled();
  fireEvent.click(toggle);
  expect(screen.getByRole("button", { name: "Hide readiness checks" })).toHaveAttribute("aria-expanded", "true");
  expect(await screen.findByRole("link", { name: "Open machine maintenance record" }))
    .toHaveAttribute("href", "/admin/machines?machine=12&detail_tab=Maintenance");
  expect(api.staffRequest).toHaveBeenCalledWith("/admin/bookings/31/readiness/", expect.any(Object));
});

it("answers an opened existing-booking check even when the server withholds it", async () => {
  api.staffRequest.mockRejectedValue(new Error("403"));
  render(<MemoryRouter><ExistingBookingReadiness bookingId={31} /></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: "Check readiness" }));
  expect(await screen.findByText("Readiness checks are unavailable for your access.")).toBeInTheDocument();
});
