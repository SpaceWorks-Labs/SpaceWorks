import { fireEvent, render as rtlRender, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// Screens now read query-backed switches (help-centre bootstrap, #184 charge flags), so every render needs a client.
function render(ui: Parameters<typeof rtlRender>[0], options?: Parameters<typeof rtlRender>[1]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children?: Parameters<typeof rtlRender>[0] }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return rtlRender(ui, { wrapper, ...options });
}
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { query, update } = vi.hoisted(() => ({
  query: vi.fn(), update: { mutate: vi.fn(), isPending: false, error: null },
}));
function mutation() { return { mutate: vi.fn(), isPending: false, error: null }; }
// The programme panels (readiness, event day, programme, add-ons) read the programme API; their own tests cover them.
vi.mock("./eventProgramme", () => ({ EventReadinessPanel: () => null, EventDayPanel: () => null }));
vi.mock("./eventProgramme/EventProgrammePanel", () => ({ EventProgrammePanel: () => null }));
vi.mock("./eventProgramme/EventAddonPanel", () => ({ EventAddonPanel: () => null }));
vi.mock("./eventsApi", () => ({ useEvent: query, useUpdateEvent: () => update,
  usePublishEvent: mutation, useCancelEvent: mutation, useCompleteEvent: mutation,
  useEventInvalidation: () => vi.fn(), useEventRegistrations: () => ({ data: { results: [] }, isLoading: false, error: null, refetch: vi.fn() }) }));
vi.mock("../../components/ui", async (importOriginal) => ({ ...await importOriginal<typeof import("../../components/ui")>(), ConfirmDialog: () => null }));
vi.mock("./EventDuplicateAction", () => ({ EventDuplicateAction: () => <p>Duplicate event</p> }));
vi.mock("./ImageUploader", () => ({ ImageUploader: () => <p>Image editor</p> }));
vi.mock("./EventCategoriesField", () => ({ EventCategoriesField: () => null }));
vi.mock("./EventInvitesPanel", () => ({ EventInvitesPanel: () => null }));
vi.mock("./EventTicketsPanel", () => ({ EventTicketsPanel: () => null }));
vi.mock("./EventPromosPanel", () => ({ EventPromosPanel: () => null }));
vi.mock("./EventRegistrationRoster", () => ({ EventRegistrationRoster: () => null }));
vi.mock("./EventFeedbackPanel", () => ({ EventFeedbackPanel: () => null }));
vi.mock("./EventFeedbackResponses", () => ({ EventFeedbackResponses: () => null }));
vi.mock("./EventCheckInOperator", () => ({ EventCheckInOperator: () => null }));
vi.mock("./EventCheckInList", () => ({ EventCheckInList: () => null }));
vi.mock("./EventSpeakersPanel", () => ({ EventSpeakersPanel: () => null }));
vi.mock("./EventBadgeActions", () => ({ EventBadgeActions: () => null }));
vi.mock("./EventOrganizers", () => ({ EventOrganizers: () => null }));
vi.mock("./EventCollaborators", () => ({ EventCollaborators: () => null }));
vi.mock("./EventStaffAccess", () => ({ EventStaffAccess: () => null }));

import { EventDrawer } from "./EventDrawer";

// Revamp SettingsRow labels both its group and its control; tests address the control.
const field = (label: string | RegExp) => screen.getAllByLabelText(label).find((el) => el.getAttribute("role") !== "group")!;

function show(permissions: string[], overrides = {}) {
  query.mockReturnValue({ data: {
    id: 4, title: "Assigned event", description: "An event", location: "Workshop",
    status: "draft", capacity: 20, payment_amount: "0.00", registration_open: true,
    updated_at: "now", starts_at: "2026-10-20T10:00:00Z", ends_at: "2026-10-20T12:00:00Z",
    timezone_name: "UTC", registration_requires_approval: false,
    registration_cutoff_at: null, registration_cutoff_lead_minutes: null,
    cancellation_cutoff_hours: null, custom_form: null, is_public: false,
    series_override_fields: [], staff_permissions: permissions, can_manage_staff: false,
    registration_counts: { registered: 0, attended: 0, waitlisted: 0, pending_approval: 0, cancelled: 0, rejected: 0 },
    ...overrides,
  } });
  // The revamp drawer is tabbed; every schedule/detail control lives on the Settings tab.
  render(<MemoryRouter initialEntries={["/?eventTab=settings"]}><EventDrawer eventId={4} makerspaceId={2} onClose={vi.fn()} /></MemoryRouter>);
}

const occurrence = { series_summary: { title: "Weekly workshop" },
  series_override_fields: ["starts_at", "ends_at", "title", "timezone_name", "payment_amount"] };
const detailLabels = ["Title", "Location", /Capacity/, /Registration audience/,
  "Tags (comma separated)", /Member cancellation closes/, "Registration cutoff",
  "Description", "Organizer approves each registration", "Anyone with the link can open this event",
  /Event time zone/];

describe("event schedule permissions", () => {
  beforeEach(() => { vi.clearAllMocks(); update.isPending = false; });

  it.each([false, true])("lets schedule-only staff reschedule (occurrence: %s) with a date-only patch", (recurring) => {
    show(["publish_schedule"], recurring ? occurrence : {});
    expect(field("Starts")).toBeEnabled();
    expect(field("Ends")).toBeEnabled();
    for (const label of detailLabels) expect(field(label)).toBeDisabled();
    expect(field(/Registration price/)).toBeDisabled();
    expect(screen.getByRole("button", { name: "Add question" })).toBeDisabled();
    expect(screen.queryByText("Image editor")).not.toBeInTheDocument();
    fireEvent.change(field("Starts"), { target: { value: "2026-10-21T10:00" } });
    fireEvent.change(field("Ends"), { target: { value: "2026-10-21T12:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(update.mutate).toHaveBeenCalledExactlyOnceWith({
      starts_at: new Date("2026-10-21T10:00").toISOString(),
      ends_at: new Date("2026-10-21T12:00").toISOString(),
    });
  });

  it("lets detail-only staff save details while locking dates and price", () => {
    show(["edit_details"]);
    expect(field("Starts")).toBeDisabled();
    expect(field("Ends")).toBeDisabled();
    for (const label of detailLabels) expect(field(label)).toBeEnabled();
    expect(field(/Registration price/)).toBeDisabled();
    fireEvent.change(field("Title"), { target: { value: "Renamed" } });
    fireEvent.change(field(/Event time zone/), { target: { value: "Asia/Kolkata" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(update.mutate).toHaveBeenCalledExactlyOnceWith({ title: "Renamed", timezone_name: "Asia/Kolkata" });
  });

  it.each(["publish_schedule", "edit_details"])("gates occurrence resets for %s", (permission) => {
    show([permission], occurrence);
    // 0.12.0: the reset buttons use plain names (EventSettings overrideFieldLabel), not the raw field keys.
    const visible = permission === "publish_schedule" ? ["start time", "end time"] : ["title", "time zone"];
    const hidden = permission === "publish_schedule" ? ["title", "time zone"] : ["start time", "end time"];
    const fieldKey: Record<string, string> = { "start time": "starts_at", "end time": "ends_at", title: "title", "time zone": "timezone_name" };
    for (const name of visible) expect(screen.getByRole("button", { name: `Reset ${name}` })).toBeEnabled();
    for (const name of [...hidden, "price"]) expect(screen.queryByRole("button", { name: `Reset ${name}` })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: `Reset ${visible[0]}` }));
    expect(update.mutate).toHaveBeenCalledExactlyOnceWith({ inherit_fields: [fieldKey[visible[0]]] });
  });

  it("retains manager detail, schedule and price edits and resets", () => {
    show([], { ...occurrence, can_manage_staff: true });
    for (const label of ["Starts", "Ends", /Registration price/, ...detailLabels]) expect(field(label)).toBeEnabled();
    expect(screen.getByRole("button", { name: "Reset price" })).toBeEnabled();
  });

  it.each(["cancelled", "completed"])("keeps %s events read-only", (status) => {
    show(["edit_details", "publish_schedule"], { ...occurrence, status });
    for (const label of ["Starts", "Ends", ...detailLabels]) expect(field(label)).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Reset/ })).not.toBeInTheDocument();
  });

  it("disables schedule saves and resets while a mutation is pending", () => {
    update.isPending = true;
    show(["publish_schedule"], occurrence);
    expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reset start time" })).toBeDisabled();
  });
});
