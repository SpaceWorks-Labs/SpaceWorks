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

const { query, occurrences, update } = vi.hoisted(() => ({ query: vi.fn(), occurrences: vi.fn(), update: vi.fn() }));
vi.mock("./eventSeriesApi", async (importOriginal) => ({ ...await importOriginal<typeof import("./eventSeriesApi")>(),
  useEventSeries: query, useEventSeriesOccurrences: occurrences,
  useUpdateEventSeries: () => ({ mutate: update }), useEventSeriesAction: () => ({ mutate: vi.fn() }) }));
vi.mock("../../components/ui", async (importOriginal) => ({ ...await importOriginal<typeof import("../../components/ui")>(), ConfirmDialog: () => null }));
vi.mock("./ImageUploader", () => ({ ImageUploader: () => <p>Series image editor</p> }));
vi.mock("./EventSeriesCollaborators", () => ({ EventSeriesCollaborators: () => <p>Series collaborators</p> }));
vi.mock("./EventStaffAccess", () => ({ EventStaffAccess: () => <p>Series staff management</p> }));
vi.mock("./EventTicketTemplates", () => ({ EventTicketTemplates: () => null }));
vi.mock("../forms/CustomFormBuilder", () => ({ CustomFormBuilder: () => null }));
import { EventSeriesDrawer } from "./EventSeriesDrawer";

describe("series grant boundaries", () => {
  beforeEach(() => {
    update.mockReset();
    occurrences.mockReturnValue({ data: { count: 1, results: [{ id: 31, starts_at: "2026-10-15T10:00:00Z", status: "published" }] } });
    query.mockReturnValue({ data: { id: 12, title: "Series", status: "draft", description: "", location: "",
      recurrence_rule: "FREQ=WEEKLY;INTERVAL=1", recurrence_timezone: "UTC", dtstart_local_date: "2026-10-15", dtstart_local_time: "10:00", duration_minutes: 60,
      capacity: 20, payment_amount: "10.00", is_public: false, custom_form: null, registration_requires_approval: false,
      registration_cutoff_lead_minutes: null, updated_at: "2026-10-14", future_occurrence_count: 0, series_override_fields: [],
      staff_permissions: [], can_manage_staff: false } });
  });
  // The series page is tabbed through the URL (seriesTab); the schedule and details editors live under Settings.
  const mount = (permissions: string[], tab = "settings") => {
    const onSelectOccurrence = vi.fn();
    query.mockReturnValue({ ...query(), data: { ...query().data, staff_permissions: permissions } });
    render(<MemoryRouter initialEntries={[`/?seriesTab=${tab}`]}><EventSeriesDrawer seriesId={12} makerspaceId={8} onClose={vi.fn()} onSelectOccurrence={onSelectOccurrence} /></MemoryRouter>);
    return onSelectOccurrence;
  };
  it("lets schedule grants edit recurrence without changing details or price", () => {
    mount(["publish_schedule"]);
    expect(screen.getByLabelText("First local date")).toBeEnabled();
    expect(screen.getByLabelText("Series title")).toBeDisabled();
    expect(screen.getByLabelText("Price per occurrence")).toBeDisabled();
    expect(screen.queryByText("Series staff management")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Duration (minutes)"), { target: { value: "90" } });
    fireEvent.click(screen.getByRole("button", { name: "Save future occurrences" }));
    expect(update).toHaveBeenCalledWith({ duration_minutes: 90 });
  });
  it("lets detail grants edit descriptions without rescheduling", () => {
    mount(["edit_details"]);
    expect(screen.getByLabelText("Series title")).toBeEnabled();
    expect(screen.getByLabelText("First local date")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Publish series" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Price per occurrence")).toBeDisabled();
  });
  it("keeps attendance grants on occurrence navigation", () => {
    const onSelectOccurrence = mount(["check_in"], "occurrences");
    expect(screen.queryByRole("button", { name: "Save future occurrences" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Occurrences" })).toBeInTheDocument();
    expect(screen.queryByText("Series collaborators")).not.toBeInTheDocument();
    expect(screen.queryByText("Series staff management")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Settings" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: (name) => name.includes(new Date("2026-10-15T10:00:00Z").toLocaleString()) }));
    expect(onSelectOccurrence).toHaveBeenCalledWith(31);
    expect(update).not.toHaveBeenCalled();
  });
});
