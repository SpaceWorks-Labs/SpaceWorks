import { cleanup, fireEvent, render as rtlRender, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// Screens now read query-backed switches (help-centre bootstrap, #184 charge flags), so every render needs a client.
function render(ui: Parameters<typeof rtlRender>[0], options?: Parameters<typeof rtlRender>[1]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children?: Parameters<typeof rtlRender>[0] }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return rtlRender(ui, { wrapper, ...options });
}
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { query } = vi.hoisted(() => ({ query: vi.fn() }));
function mutation() { return { mutate: vi.fn(), isPending: false, error: null }; }
// The programme panels (readiness, event day, programme, add-ons) read the programme API; their own tests cover them.
vi.mock("./eventProgramme", () => ({ EventReadinessPanel: () => null, EventDayPanel: () => null }));
vi.mock("./eventProgramme/EventProgrammePanel", () => ({ EventProgrammePanel: () => null }));
vi.mock("./eventProgramme/EventAddonPanel", () => ({ EventAddonPanel: () => null }));
vi.mock("./eventsApi", () => ({ useEvent: query,
  useUpdateEvent: mutation, usePublishEvent: mutation, useCancelEvent: mutation,
  useCompleteEvent: mutation, useEventInvalidation: () => vi.fn(),
  useEventRegistrations: () => ({ data: { results: [] }, isLoading: false, error: null, refetch: vi.fn() }) }));
vi.mock("../../components/ui", async (importOriginal) => ({ ...await importOriginal<typeof import("../../components/ui")>(), ConfirmDialog: () => null }));
vi.mock("./EventFormFields", () => ({ EventFields: ({ canEditDetails, canEditSchedule }: { canEditDetails: boolean; canEditSchedule: boolean }) => <>{canEditDetails ? <p>Details editor</p> : null}{canEditSchedule ? <p>Schedule editor</p> : null}</>, emptyEventForm: {}, payloadFor: vi.fn(), valuesFor: () => ({}) }));
vi.mock("./EventDuplicateAction", () => ({ EventDuplicateAction: () => <p>Duplicate event</p> }));
vi.mock("./ImageUploader", () => ({ ImageUploader: () => <p>Image editor</p> }));
vi.mock("./eventProgramme/EventCoverUploader", () => ({ EventCoverUploader: () => <p>Image editor</p> }));
vi.mock("./EventCategoriesField", () => ({ EventCategoriesField: () => <p>Tenant categories</p> }));
vi.mock("./EventInvitesPanel", () => ({ EventInvitesPanel: () => <p>Registration invitations</p> }));
// A21: registration staff read the ticket types; only managers get the editable panel.
vi.mock("./EventTicketsPanel", () => ({ EventTicketsPanel: ({ readOnly }: { readOnly?: boolean }) => <p>{readOnly ? "Ticket list" : "Ticket payments"}</p> }));
vi.mock("./EventPromosPanel", () => ({ EventPromosPanel: () => <p>Promo payments</p> }));
vi.mock("./EventRegistrationRoster", () => ({ EventRegistrationRoster: () => <p>Registration roster</p> }));
vi.mock("./EventFeedbackPanel", () => ({ EventFeedbackPanel: () => <p>Survey editor</p> }));
vi.mock("./EventFeedbackResponses", () => ({ EventFeedbackResponses: () => <p>Survey responses</p> }));
vi.mock("./EventCheckInOperator", () => ({ EventCheckInOperator: ({ canManageStation }: { canManageStation: boolean }) => <p>{canManageStation ? "Station controls" : "Attendance scanner"}</p> }));
vi.mock("./EventCheckInList", () => ({ EventCheckInList: () => <p>Checked-in list</p> }));
vi.mock("./EventSpeakersPanel", () => ({ EventSpeakersPanel: () => <p>Speaker management</p> }));
vi.mock("./EventBadgeActions", () => ({ EventBadgeActions: () => <p>Badge editor</p> }));
vi.mock("./EventOrganizers", () => ({ EventOrganizers: () => <p>Organizer management</p> }));
vi.mock("./EventCollaborators", () => ({ EventCollaborators: () => <p>Collaborator management</p> }));
vi.mock("./EventStaffAccess", () => ({ EventStaffAccess: () => <p>Staff access management</p> }));

import { EventDrawer } from "./EventDrawer";

const panels: Record<string, string[]> = {
  edit_details: ["Details editor", "Image editor", "Survey editor", "Badge editor", "Speaker management"],
  manage_registrations: ["Registration roster", "Survey responses", "Ticket list"],
  manage_invitations: ["Registration invitations"],
  check_in: ["Attendance scanner", "Checked-in list"],
  publish_schedule: ["Publish", "Schedule editor"],
};
const managerOnly = ["Ticket payments", "Promo payments", "Staff access management", "Organizer management", "Collaborator management", "Tenant categories", "Station controls"];
// The revamp drawer is tabbed: a surface counts as reachable when any tab the viewer has renders it.
// Legacy keys (tickets, team, settings, …) now open sections of the More tab and must keep working.
const TABS = ["overview", "registrations", "checkin", "more", "tickets", "speakers", "feedback", "broadcasts", "analytics", "website", "team", "settings"];
const counts = { registered: 0, attended: 0, waitlisted: 0, pending_approval: 0, cancelled: 0, rejected: 0 };
const base = { id: 4, title: "Assigned event", description: "An event", capacity: 20, registration_open: true,
  updated_at: "now", series_override_fields: [], registration_counts: counts, payment_amount: "0.00",
  starts_at: new Date().toISOString(), ends_at: new Date(Date.now() + 3_600_000).toISOString(), timezone_name: "UTC",
  ticketing_features: ["events.invites", "events.ticket_types", "events.promo_codes"],
  offline_checkin_enabled: true, staff_permissions: [] as string[], can_manage_staff: false };

function renderTab(tab: string) {
  return render(<MemoryRouter initialEntries={[`/?eventTab=${tab}`]}><EventDrawer eventId={4} makerspaceId={2} onClose={vi.fn()} /></MemoryRouter>);
}
function present(label: string) {
  return screen.queryAllByText(label).length > 0 || screen.queryAllByRole("button", { name: new RegExp(`^${label}…?$`) }).length > 0;
}
function reachable(labels: string[]) {
  const seen = new Set<string>();
  for (const tab of TABS) { renderTab(tab); for (const label of labels) if (present(label)) seen.add(label); cleanup(); }
  return seen;
}
function show(data: Partial<typeof base> & { status: string }) { query.mockReturnValue({ data: { ...base, ...data } }); }

describe("event drawer permission surfaces", () => {
  beforeEach(() => show({ status: "draft" }));
  it.each(Object.keys(panels))("shows only the %s surfaces", (permission) => {
    // Check-in exists only once an event is live; every other grant is exercised on a draft.
    show({ status: permission === "check_in" ? "published" : "draft", staff_permissions: [permission] });
    const seen = reachable([...Object.values(panels).flat(), ...managerOnly]);
    for (const [other, labels] of Object.entries(panels)) for (const label of labels) {
      expect(seen.has(label), `${permission}: ${label}`).toBe(other === permission);
    }
    for (const label of managerOnly) expect(seen.has(label), `${permission}: ${label}`).toBe(false);
  });
  it("retains all manager operations", () => {
    show({ status: "draft", can_manage_staff: true });
    const seen = reachable(["Details editor", "Staff access management", "Ticket payments"]);
    expect([...seen].sort()).toEqual(["Details editor", "Staff access management", "Ticket payments"]);
    renderTab("overview");
    fireEvent.click(screen.getByRole("button", { name: /^Publish/ }));
  });
  it.each([
    ["edit_details", false, false], ["manage_registrations", true, false], ["check_in", false, true],
  ])("offers overview jumps only for held tabs (%s)", (permission, registrations, checkIn) => {
    show({ status: "published", staff_permissions: [permission] });
    renderTab("overview");
    expect(Boolean(screen.queryByRole("button", { name: "All registrations" }))).toBe(registrations);
    expect(Boolean(screen.queryByRole("button", { name: "Prepare check-in" }))).toBe(checkIn);
  });
});
