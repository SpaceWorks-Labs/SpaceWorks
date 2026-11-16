import { fireEvent, render as rtlRender, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// Screens now read query-backed switches (help-centre bootstrap, #184 charge flags), so every render needs a client.
function render(ui: Parameters<typeof rtlRender>[0], options?: Parameters<typeof rtlRender>[1]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children?: Parameters<typeof rtlRender>[0] }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return rtlRender(ui, { wrapper, ...options });
}
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { query, update } = vi.hoisted(() => ({ query: vi.fn(), update: { mutate: vi.fn(), isPending: false, error: null } }));
function mutation() { return { mutate: vi.fn(), isPending: false, error: null }; }
// The programme panels (readiness, event day, programme, add-ons) read the programme API; their own tests cover them.
vi.mock("./eventProgramme", () => ({ EventReadinessPanel: () => null, EventDayPanel: () => null }));
vi.mock("./eventProgramme/EventProgrammePanel", () => ({ EventProgrammePanel: () => null }));
vi.mock("./eventProgramme/EventAddonPanel", () => ({ EventAddonPanel: () => null }));
vi.mock("./eventsApi", () => ({ useEvent: query, useUpdateEvent: () => update,
  usePublishEvent: mutation, useCancelEvent: mutation, useCompleteEvent: mutation, useEventInvalidation: () => vi.fn(),
  useEventRegistrations: () => ({ data: { results: [] }, isLoading: false, error: null, refetch: vi.fn() }) }));
vi.mock("../../components/ui", async (importOriginal) => ({ ...await importOriginal<typeof import("../../components/ui")>(), ConfirmDialog: () => null }));
vi.mock("./EventSettings", () => ({ EventSettings: () => <p>Full settings form</p> }));
vi.mock("./EventInvitesPanel", () => ({ EventInvitesPanel: ({ visible }: { visible: boolean }) => visible ? <p>Invitations panel</p> : null }));
vi.mock("./EventTicketsPanel", () => ({ EventTicketsPanel: ({ visible }: { visible: boolean }) => visible ? <p>Ticket types panel</p> : null }));
vi.mock("./EventPromosPanel", () => ({ EventPromosPanel: () => null }));
vi.mock("./EventRegistrationRoster", () => ({ EventRegistrationRoster: () => null }));
vi.mock("./EventFeedbackPanel", () => ({ EventFeedbackPanel: () => <p>Feedback panel</p> }));
vi.mock("./EventFeedbackResponses", () => ({ EventFeedbackResponses: () => null }));
vi.mock("./EventCheckInOperator", () => ({ EventCheckInOperator: () => <p>Attendance scanner</p> }));
vi.mock("./EventCheckInList", () => ({ EventCheckInList: () => <p>Checked-in list</p> }));
vi.mock("./EventSpeakersPanel", () => ({ EventSpeakersPanel: () => <p>Speakers panel</p> }));
vi.mock("./EventOrganizers", () => ({ EventOrganizers: ({ visible }: { visible: boolean }) => visible ? <p>Organizers panel</p> : null }));
vi.mock("./EventCollaborators", () => ({ EventCollaborators: () => null }));
vi.mock("./EventStaffAccess", () => ({ EventStaffAccess: () => <p>Staff access panel</p> }));
vi.mock("./EventAudienceOrganizations", () => ({ EventAudienceOrganizations: () => null }));
vi.mock("./EventDuplicateAction", () => ({ EventDuplicateAction: () => null }));

import { EventDrawer } from "./EventDrawer";

const counts = { registered: 0, attended: 0, waitlisted: 0, pending_approval: 0, cancelled: 0, rejected: 0 };
function show(tab: string | null, overrides: Record<string, unknown> = {}, enabledFeatures: string[] = []) {
  query.mockReturnValue({ data: {
    id: 4, title: "Repair night", description: "", location: "Workshop", status: "draft", capacity: 20, payment_amount: "0.00",
    registration_open: true, updated_at: "now", starts_at: "2026-10-20T10:00:00Z", ends_at: "2026-10-20T12:00:00Z",
    timezone_name: "UTC", registration_requires_approval: false, registration_cutoff_at: null, registration_cutoff_lead_minutes: null,
    cancellation_cutoff_hours: null, custom_form: null, is_public: false, series_override_fields: [], series_summary: null,
    staff_permissions: [], can_manage_staff: true, registration_counts: counts, offline_checkin_enabled: false,
    ticketing_features: ["events.invites", "events.ticket_types"], ...overrides,
  } });
  render(<MemoryRouter initialEntries={[tab ? `/?eventTab=${tab}` : "/"]}><EventDrawer eventId={4} makerspaceId={2} onClose={vi.fn()} enabledFeatures={enabledFeatures} /></MemoryRouter>);
}
const nav = (name: string) => screen.getByRole("navigation", { name });
const labels = (name: string) => within(nav(name)).getAllByRole("link").map((link) => link.textContent?.replace(/\s*\d+$/, ""));
const current = (name: string) => within(nav(name)).getAllByRole("link").find((link) => link.getAttribute("aria-current") === "page")?.textContent;

describe("event drawer tabs", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("orders the top tabs Overview, Registrations, Check-in, More", () => {
    show(null);
    expect(labels("Page sections")).toEqual(["Overview", "Registrations", "Check-in", "More"]);
    expect(screen.queryByRole("navigation", { name: "More sections" })).toBeNull();
  });

  it("keeps Check-in visible on a draft and explains it opens on publish", () => {
    show("checkin", { can_manage_staff: false, staff_permissions: ["check_in"] });
    expect(labels("Page sections")).toContain("Check-in");
    expect(screen.getByRole("heading", { name: "Check-in opens once the event is published" })).toBeVisible();
    expect(screen.queryByText("Attendance scanner")).toBeNull();
  });

  it("shows the scanner once the event is published", () => {
    show("checkin", { status: "published" });
    expect(screen.getByText("Attendance scanner")).toBeInTheDocument();
    expect(screen.queryByText("Check-in opens once the event is published")).toBeNull();
  });

  it.each([
    ["tickets", "Tickets & invites", "Ticket types panel"],
    ["team", "Team", "Organizers panel"],
    ["settings", "Settings", "Full settings form"],
    ["feedback", "Feedback", "Feedback panel"],
    ["speakers", "Speakers", "Speakers panel"],
  ])("maps the legacy ?eventTab=%s link into More", (key, section, panel) => {
    show(key);
    expect(current("Page sections")).toBe("More");
    expect(current("More sections")).toBe(section);
    expect(screen.getByText(panel)).toBeInTheDocument();
  });

  it("opens the first available section from the More tab and lists every held section", () => {
    show("more");
    expect(current("More sections")).toBe("Tickets & invites");
    expect(labels("More sections")).toEqual(["Tickets & invites", "Speakers", "Feedback", "Team", "Settings", "Stage forms"]);
    fireEvent.click(within(nav("More sections")).getByRole("link", { name: "Speakers" }));
    expect(screen.getByText("Speakers panel")).toBeInTheDocument();
  });

  it.each([
    [["events.id_cards"], [], "ID cards"],
    [["events.ticket_designs"], [], "Ticket design"],
    [["events.id_cards", "events.ticket_designs"], [], "Cards and tickets"],
    [[], ["events.certificate_designer"], "Certificates"],
    [["events.id_cards"], ["events.certificate_designer"], "Certificates and ID cards"],
    [["events.ticket_designs"], ["events.certificate_designer"], "Certificates and tickets"],
    [["events.id_cards", "events.ticket_designs"], ["events.certificate_designer"], "Certificates, cards and tickets"],
  ])("opens independent credential tools with an accurate label: %s", (features, ticketing, label) => {
    show("certificates", { ticketing_features: ticketing }, features);
    expect(current("More sections")).toBe(label);
  });

  it("does not grant card-only navigation to check-in staff", () => {
    show("more", { can_manage_staff: false, staff_permissions: ["check_in"], ticketing_features: [] }, ["events.id_cards", "events.ticket_designs"]);
    expect(screen.queryByRole("navigation", { name: "More sections" })).toBeNull();
    expect(labels("Page sections")).toEqual(["Overview", "Check-in"]);
  });

  it("edits the essentials inline and sends only the changed fields", () => {
    show(null);
    fireEvent.click(screen.getByRole("button", { name: "Edit essentials" }));
    const form = screen.getByRole("form", { name: "Edit essentials" });
    expect(within(form).queryByLabelText("Description")).toBeNull();
    fireEvent.change(within(form).getByLabelText("Title"), { target: { value: "Repair café" } });
    fireEvent.change(within(form).getByLabelText(/^Capacity/), { target: { value: "30" } });
    fireEvent.click(within(form).getByRole("button", { name: "Save essentials" }));
    expect(update.mutate).toHaveBeenCalledExactlyOnceWith({ title: "Repair café", capacity: 30 }, expect.objectContaining({ onSuccess: expect.any(Function) }));
  });

  it("hides the essentials editor from staff who can't edit, and from closed events", () => {
    show(null, { can_manage_staff: false, staff_permissions: ["check_in"] });
    expect(screen.queryByRole("button", { name: "Edit essentials" })).toBeNull();
  });
});
