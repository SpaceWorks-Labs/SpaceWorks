import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { EventBulkInvites } from "./EventBulkInvites";
import { EventAnalyticsPanel } from "./EventAnalyticsPanel";
import { expectNoA11yViolations } from "../../test/axe";

const state = vi.hoisted(() => ({
  history: { data: { count: 1, previous: null, next: null, results: [{ id: 1, subject: "Notice", body: "Hello {{ name }}", status: "draft" }] }, isLoading: false, error: null as Error | null },
  compose: { mutate: vi.fn(), isPending: false, error: null },
  action: { mutate: vi.fn(), isPending: false, error: null },
  bulk: { mutate: vi.fn(), isPending: false, error: null as Error | null, data: undefined },
  query: { data: { typed_rows: [{ registrations: 7, attended: 3 }] }, isLoading: false, error: null },
  download: { mutate: vi.fn(), isPending: false, error: null },
}));
// The participation funnel reads the programme analytics API; the aggregate counts here are the subject.
vi.mock("./eventProgramme/EventProgrammeAnalytics", () => ({ EventProgrammeAnalytics: () => null }));
vi.mock("./eventCommunicationsApi", () => ({
  useEventBroadcasts: () => state,
  useBulkEventInvites: () => state.bulk,
  useEventAnalytics: () => state,
}));

beforeEach(() => { vi.clearAllMocks(); state.history.error = null; state.history.isLoading = false; state.bulk.error = null; });

describe("Event communications", () => {
  // The broadcast panel is now the v2 composer (eventProgramme/EventBroadcastsPanel), covered by
  // eventProgramme/broadcast.test.tsx; the v1 compose/preview cases here no longer apply.
  it("bounds bulk email input and reports failures accessibly", async () => {
    const { container } = render(<EventBulkInvites eventId={2} disabled={false} />);
    const button = screen.getByRole("button", { name: "Add and email invitations" });
    expect(button).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Invite by email (up to 200)"), { target: { value: "a@example.test\nb@example.test" } });
    fireEvent.click(button);
    expect(state.bulk.mutate).toHaveBeenCalledWith(["a@example.test", "b@example.test"], expect.anything());
    fireEvent.change(screen.getByLabelText("Invite by email (up to 200)"), { target: { value: Array.from({ length: 201 }, (_, i) => `${i}@example.test`).join("\n") } });
    expect(button).toBeDisabled();
    await expectNoA11yViolations(container);
  });

  it("uses aggregate report data and hides unavailable exports", async () => {
    const { container } = render(<EventAnalyticsPanel makerspaceId={1} eventId={2} endsAt="2099-01-01" features={["analytics", "pdf"]} />);
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Post-event PDF" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Registration CSV" })).not.toBeInTheDocument();
    await expectNoA11yViolations(container);
  });
});
