import { formatDateTime } from "../../lib/format";
import { MemoryRouter } from "react-router-dom";
import { TenantProvider } from "../../lib/tenant";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { MemberActivityPanel, type MemberActivity } from "./MemberActivity";

vi.mock("../../lib/api", () => ({ memberRequest: vi.fn(), staffRequest: vi.fn(), staffRequestBlob: vi.fn() }));
vi.mock("./MemberCalendarActions", () => ({ MemberCalendarActions: () => <p>Calendar controls</p> }));
vi.mock("./MemberEventFeedback", () => ({ MemberEventFeedback: () => <p>Feedback controls</p> }));

const modules = ["membership", "request_workflow", "machines", "machine_service", "bookings", "events", "presence"];
const activity: MemberActivity = {
  active_hardware_loans: [{ request_id: 12, can_renew: true, label: "Drill", checked_out_at: "2026-10-01", due_at: "2026-10-12", overdue: false }],
  machine_service_requests: [{ machine_type: "3d_printer", title: "Print job", status: "queued", queue_position: 2 }],
  bookings: { upcoming: [{ space_name: "Bench", starts_at: "2026-11-01", ends_at: "2026-11-02", status: "confirmed" }], past: [] },
  event_registrations: [{ registration_id: 3, event_title: "Workshop", starts_at: "2026-11-01", status: "registered", waitlist_position: null,
    can_cancel: false, cancellation_cutoff_at: "2026-10-20T12:00:00Z", checkin_token: "qr-token", feedback_available: true, feedback_path: "/feedback", certificate: null }],
  recent_presence_sessions: [], currently_checked_in: false,
  accountability: { membership_active: true, waiver_acceptance_required: true, restriction_code: null },
};
function show(section?: "overview" | "loans" | "bookings" | "events", enabled = modules, data = activity) {
  return render(<QueryClientProvider client={new QueryClient()}>
    <MemoryRouter><TenantProvider><MemberActivityPanel section={section} modules={enabled} activity={data} makerspaceId={7} makerspaceSlug="lab" makerspaceName="Lab" /></TenantProvider></MemoryRouter>
  </QueryClientProvider>);
}

it.each([
  ["overview", ["My activity", "3D print requests", "Recent presence"]],
  ["loans", ["Active loans"]],
  ["bookings", ["Bookings"]],
  // The events section also lists the member's certificates and signatory approvals (9e09d158, a01362e8).
  ["events", ["Event registrations", "Certificates"]],
] as const)("renders only the %s sections", (section, titles) => {
  show(section);
  expect(screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent)).toEqual(titles);
});

it("keeps the full activity view when no section is selected", () => {
  show();
  expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(7); // six areas plus Certificates
  expect(screen.getByRole("button", { name: "Renew loan" })).toBeVisible();
});

it("hides stale domain data and actions when modules are disabled", () => {
  show(undefined, ["membership"]);
  expect(screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent)).toEqual(["My activity"]);
  expect(screen.queryByRole("button", { name: "Renew loan" })).toBeNull();
  expect(screen.queryByText("Calendar controls")).toBeNull();
  expect(screen.queryByRole("button", { name: "Show check-in QR" })).toBeNull();
});

it("honours the server's cancellation refusal while retaining QR, feedback and calendar controls", () => {
  show("events");
  expect(screen.getByText("The cancellation deadline has passed. Contact staff.")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Cancel registration" })).toBeNull();
  expect(screen.getByRole("button", { name: "Show check-in QR" })).toBeVisible();
  expect(screen.getByText("Feedback controls")).toBeVisible();
  expect(screen.getByText("Calendar controls")).toBeVisible();
});

it("shows the server's cancellation cutoff when cancellation is allowed", () => {
  const cutoff = activity.event_registrations![0].cancellation_cutoff_at!;
  show("events", modules, { ...activity, event_registrations: [{ ...activity.event_registrations![0], can_cancel: true }] });
  expect(screen.getByText(`Cancel before ${formatDateTime(cutoff)}.`)).toBeVisible();
  expect(screen.getByRole("button", { name: "Cancel registration" })).toBeVisible();
});

it("shows the server ETA and an owner Cancel that confirms, posts and refetches activity", async () => {
  const { memberRequest } = await import("../../lib/api");
  vi.mocked(memberRequest).mockResolvedValue({ status: "cancelled" });
  const { fireEvent, waitFor } = await import("@testing-library/react");
  const { expectNoA11yViolations } = await import("../../test/axe");
  const withEta: MemberActivity = { ...activity, machine_service_requests: [
    { request_id: 41, can_cancel: true, public_token: "tok-1", machine_type: "3d_printer", machine_type_name: "3D printer",
      title: "Print job", status: "accepted", queue_position: 1, eta: { calculated_at: "2026-10-18T10:00:00Z",
        estimated_start_at: "2026-10-18T10:50:00Z", estimated_finish_at: "2026-10-18T11:05:00Z", start_in_minutes: 50,
        finish_in_minutes: 65, confidence: "estimated", reasons: [], approved_ahead: 0, awaiting_review_ahead: 0,
        active_machine_count: 2, missing_estimate_count: 0 } },
    { request_id: 42, can_cancel: false, public_token: "tok-2", machine_type_name: "Laser cutter", title: "Laser job",
      status: "cancelled", queue_position: null, eta: null },
  ] };
  const { container } = show("overview", modules, withEta);
  expect(screen.getByText(/Starts in about 50 min/)).toBeInTheDocument();
  expect(screen.getByText("You're next among approved jobs")).toBeInTheDocument();
  expect(screen.getByText("Cancelled")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Cancel job" })).toHaveLength(1);
  expect(screen.getAllByRole("link", { name: "Track job" })[0]).toHaveAttribute("href", "/m/lab/machine-service/requests/tok-1");
  await expectNoA11yViolations(container);
  fireEvent.click(screen.getByRole("button", { name: "Cancel job" }));
  fireEvent.click(await screen.findByRole("button", { name: "Yes, cancel job" }));
  await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/member/machine-service/requests/41/cancel", expect.objectContaining({ method: "POST" })));
});
