import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EventCheckInScanner from "./EventCheckInScanner";

const mocks = vi.hoisted(() => ({ resolve: vi.fn(), attend: vi.fn(), correct: vi.fn() }));
vi.mock("./eventsApi", () => ({
  useResolveEventCheckIn: () => ({ mutateAsync: mocks.resolve, isPending: false }),
  useMarkEventAttended: () => ({ mutateAsync: mocks.attend, isPending: false }),
}));
vi.mock("./eventFeedbackApi", () => ({ useCorrectAttendance: () => ({ mutate: mocks.correct, isPending: false }) }));
vi.mock("./eventsBadgeApi", () => ({ useGenerateEventBadges: () => ({ mutate: vi.fn(), isPending: false }) }));
// The quick badge dialog after a check-in reads the credentials API; its own tests cover it.
vi.mock("./eventCredentials/QuickBadgePrint", () => ({ QuickBadgePrint: () => null }));
const guest = { registration_id: 42, name: "Priya", status: "registered", event_status: "published", confirmable: true, payment_status: "unpaid", host_waiver_state: "missing" };
beforeEach(() => { vi.clearAllMocks(); mocks.resolve.mockResolvedValue(guest); mocks.attend.mockResolvedValue({}); });
function show() { render(<EventCheckInScanner makerspaceId={3} eventId={8} onClose={vi.fn()} />); }
async function findGuest() {
  fireEvent.change(screen.getByRole("searchbox", { name: "Find a guest by check-in code" }), { target: { value: "  event-code  " } });
  fireEvent.click(screen.getByRole("button", { name: "Find" }));
  return screen.findByRole("button", { name: "Confirm attendance" });
}
describe("event ScanWorkbench", () => {
  it("resolves before confirming and retains the existing attendance reversal", async () => {
    show();
    const confirm = await findGuest();
    expect(mocks.resolve).toHaveBeenCalledWith("event-code");
    expect(mocks.attend).not.toHaveBeenCalled();
    expect(screen.getByText("Payment: unpaid")).toBeVisible();
    expect(screen.getByText(/No host waiver on file/)).toBeVisible();
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);
    await waitFor(() => expect(mocks.attend).toHaveBeenCalledWith(42));
    // The reversal now sits with the attendance tools (print badge / correct attendance) under the result.
    fireEvent.click(await screen.findByRole("button", { name: "Correct attendance" }));
    expect(mocks.correct).toHaveBeenCalledWith(42, expect.objectContaining({ onSuccess: expect.any(Function) }));
  });
  it("never confirms a waitlisted registration", async () => {
    mocks.resolve.mockResolvedValue({ ...guest, status: "waitlisted", confirmable: false });
    show();
    expect(await findGuest()).toBeDisabled();
    expect(screen.getByText(/Waitlisted registrations cannot be checked in/, { selector: "p" })).toBeVisible();
    expect(mocks.attend).not.toHaveBeenCalled();
  });
  it("shows resolution failures without offering an attendance mutation", async () => {
    mocks.resolve.mockRejectedValue(new Error("That is not a check-in code for this event."));
    show();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "wrong-event" } });
    fireEvent.click(screen.getByRole("button", { name: "Find" }));
    expect(await screen.findByText("That is not a check-in code for this event.")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Confirm attendance" })).toBeNull();
    expect(mocks.attend).not.toHaveBeenCalled();
  });
});
