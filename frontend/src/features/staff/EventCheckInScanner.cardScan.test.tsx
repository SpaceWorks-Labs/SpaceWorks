import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import EventCheckInScanner from "./EventCheckInScanner";

const mocks = vi.hoisted(() => ({ resolve: vi.fn(), attend: vi.fn(), request: vi.fn() }));
vi.mock("./eventsApi", () => ({
  useResolveEventCheckIn: () => ({ mutateAsync: mocks.resolve, isPending: false }),
  useMarkEventAttended: () => ({ mutateAsync: mocks.attend, isPending: false }),
}));
vi.mock("../../lib/api", async () => ({ ...(await vi.importActual<typeof import("../../lib/api")>("../../lib/api")),
  staffRequest: mocks.request }));
vi.mock("./eventFeedbackApi", () => ({ useCorrectAttendance: () => ({ mutate: vi.fn(), isPending: false }) }));
vi.mock("./eventsBadgeApi", () => ({ useGenerateEventBadges: () => ({ mutate: vi.fn(), isPending: false }) }));
vi.mock("./eventCredentials/QuickBadgePrint", () => ({ QuickBadgePrint: () => null }));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.resolve.mockRejectedValue(new StructuredApiError(404, { detail: "Not found." }));
  mocks.attend.mockResolvedValue({});
});

function scan(value: string) {
  render(<EventCheckInScanner makerspaceId={3} eventId={8} onClose={vi.fn()} />);
  fireEvent.change(screen.getByRole("searchbox"), { target: { value } });
  fireEvent.click(screen.getByRole("button", { name: "Find" }));
}

describe("door scanner with a card (#132d1)", () => {
  it("finds one registration by card and checks it in through the card route after confirming", async () => {
    mocks.request.mockImplementation((_path: string, init: { body: string }) => Promise.resolve(JSON.parse(init.body).check_in
      ? { checked_in: 42, registrations: [{ registration_id: 42, name: "Priya", status: "registered", confirmable: true }] }
      : { checked_in: null, registrations: [{ registration_id: 42, name: "Priya", status: "registered", confirmable: true }] }));
    scan("0123456789abcdef0123456789abcdef");
    const confirm = await screen.findByRole("button", { name: "Confirm attendance" });
    expect(mocks.request).toHaveBeenCalledWith("/admin/events/8/check-in/card-scan", expect.objectContaining({
      body: JSON.stringify({ payload: "0123456789abcdef0123456789abcdef", check_in: false }) }));
    fireEvent.click(confirm);
    expect(await screen.findAllByText("Priya checked in.")).not.toHaveLength(0);
    expect(mocks.attend).not.toHaveBeenCalled();
  });

  it("lists several registrations for staff to pick, through the normal check-in", async () => {
    mocks.request.mockResolvedValue({ checked_in: null, registrations: [
      { registration_id: 1, name: "Priya", status: "attended", confirmable: false },
      { registration_id: 2, name: "Priya R", status: "registered", confirmable: true }] });
    scan("card");
    expect(await screen.findByRole("button", { name: "Check in Priya" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Check in Priya R" }));
    await waitFor(() => expect(mocks.attend).toHaveBeenCalledWith(2));
  });

  it("says plainly when the code is neither a ticket nor a card", async () => {
    mocks.request.mockRejectedValue(new StructuredApiError(404, { detail: "Not found." }));
    scan("nonsense");
    expect(await screen.findByText("That is not a check-in code or a card for this event.")).toBeVisible();
  });
});
