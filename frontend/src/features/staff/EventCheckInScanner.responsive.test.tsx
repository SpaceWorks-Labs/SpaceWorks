import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import EventCheckInScanner from "./EventCheckInScanner";

const mocks = vi.hoisted(() => ({ resolve: vi.fn(), attend: vi.fn() }));
vi.mock("./eventsApi", () => ({
  useResolveEventCheckIn: () => ({ mutateAsync: mocks.resolve, isPending: false }),
  useMarkEventAttended: () => ({ mutateAsync: mocks.attend, isPending: false }),
}));
vi.mock("./eventFeedbackApi", () => ({ useCorrectAttendance: () => ({ mutate: vi.fn(), isPending: false }) }));
afterEach(() => { delete (Element.prototype as Partial<Element>).scrollIntoView; });

it("brings the scanned guest and the Confirm button into view at the door", async () => {
  const scrolled: Element[] = [];
  Element.prototype.scrollIntoView = function (this: Element) { scrolled.push(this); };
  mocks.resolve.mockResolvedValue({ registration_id: 4, name: "Priya", status: "registered", event_status: "published", confirmable: true, payment_status: null, host_waiver_state: "on_file" });
  render(<EventCheckInScanner makerspaceId={1} eventId={2} onClose={vi.fn()} />);
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "code" } });
  fireEvent.click(screen.getByRole("button", { name: "Find" }));
  const confirm = await screen.findByRole("button", { name: "Confirm attendance" });
  await waitFor(() => expect(scrolled.some(element => element.contains(confirm))).toBe(true));
});
