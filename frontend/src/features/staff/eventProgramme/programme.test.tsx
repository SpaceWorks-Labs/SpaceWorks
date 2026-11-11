import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { staffRequest, StructuredApiError } from "../../../lib/api";
import { EventReadinessPanel } from "./EventReadinessPanel";
import { EventDayPanel } from "./EventDayPanel";
import { EventPublishingPanel } from "./EventPublishingPanel";
import { EventFunnel } from "./EventFunnel";
import { AccentPresetPicker } from "./AccentPresetPicker";
import { WordFeedbackRating } from "./WordFeedbackRating";
import { ProgrammeFormEditor } from "./ProgrammeFormEditor";
import { NextUpEvents } from "./NextUpEvents";
vi.mock("../../../lib/api", async importOriginal => ({ ...await importOriginal<typeof import("../../../lib/api")>(), staffRequest: vi.fn() }));
function mount(element: React.ReactNode, client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })) { return render(<MemoryRouter><QueryClientProvider client={client}>{element}</QueryClientProvider></MemoryRouter>); }
beforeEach(() => { vi.mocked(staffRequest).mockReset(); });
it("renders only returned permission-filtered readiness checks", async () => {
  vi.mocked(staffRequest).mockResolvedValue({ items: [{ code: "cover", label: "Add a cover", status: "missing", href: "/admin/events", count: null }, { code: "review", label: "Review applications", status: "action", href: "/admin/events", count: 3 }] });
  mount(<EventReadinessPanel eventId={42} />);
  expect(await screen.findByText("Review applications")).toBeVisible(); expect(screen.getByText("3")).toBeVisible(); expect(screen.queryByText("Judge coverage")).not.toBeInTheDocument();
});
it("shows zero-safe checkin meter and first-run state", async () => {
  vi.mocked(staffRequest).mockResolvedValue({ active: true, going: 0, checked_in: 0, seconds_until_doors: 600, arrivals: [], first_run: true });
  mount(<EventDayPanel eventId={42} />); expect(await screen.findByText(/No arrivals yet/)).toBeVisible(); expect(screen.getByRole("meter")).toHaveAttribute("max", "1");
});
it("preserves publishing edits after stale save and never implies website release", async () => {
  const row = { event_id: 42, version: 4, is_public: false, registration_audience: "members", status: "draft", website_revision: 2, website_released: false };
  vi.mocked(staffRequest).mockImplementation(async (_path, options) => { if (options?.method === "PATCH") throw new Error("stale_version"); return row; });
  mount(<EventPublishingPanel eventId={42} />); const visibility = await screen.findByRole("radio", { name: /Anyone with the link/ }); fireEvent.click(visibility); fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(await screen.findByText(/stale_version/)).toBeVisible(); expect(visibility).toBeChecked();
  const call = vi.mocked(staffRequest).mock.calls.find(([, options]) => options?.method === "PATCH")!;
  const input = JSON.parse(String(call[1]?.body)); expect(input).toMatchObject({ expected_version: 4, is_public: true, release_saved_website: false }); expect(call[1]?.headers).toEqual({ "Idempotency-Key": input.operation_id });
  fireEvent.click(screen.getByRole("button", { name: "Discard" })); await waitFor(() => expect(screen.getByRole("radio", { name: /Only your team/ })).toBeChecked());
});
it("caps funnel shares visually and retains denominators and caveat", () => {
  mount(<EventFunnel data={{ event_id: 42, timezone_name: "Asia/Kolkata", stages: [{ key: "going", label: "Going", count: 12, denominator: 10, percent: 120 }], timeline: [], capacity: { limit: 10, going: 12, remaining: 0, state: "over_capacity" }, caveat: "Missing historical responses.", reading: "Twelve people are going.", hint: "Review capacity." }} />);
  expect(screen.getByRole("progressbar")).toHaveAttribute("value", "100"); expect(screen.getByText("12 of 10 · 120%")).toBeVisible(); expect(screen.getByText("Missing historical responses.")).toBeVisible();
});
it("accepts only brand preset choices and inheritance", () => {
  const change = vi.fn(); mount(<AccentPresetPicker value={null} onChange={change} />); fireEvent.click(screen.getByRole("radio", { name: "Maker Teal" })); expect(change).toHaveBeenCalledWith("maker_teal"); expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
});
it("preserves explicit historical numeric rating meanings", () => {
  const change = vi.fn(); mount(<WordFeedbackRating schemaVersion={1} id="rating" label="How was the workshop?" values={{ Excellent: 5, Good: 4, Okay: 3, Poor: 1 }} value={4} onChange={change} />);
  expect(screen.getByRole("radio", { name: "Good, selected" })).toBeChecked(); fireEvent.click(screen.getByRole("radio", { name: "Excellent" })); expect(change).toHaveBeenCalledWith(5);
});
it("writes v2 stable option IDs for word ratings", () => {
  const change = vi.fn(); mount(<WordFeedbackRating schemaVersion={2} id="rating" label="How was the workshop?" values={{ Excellent: "great", Good: "good", Okay: "ok", Poor: "poor" }} value={undefined} onChange={change} />);
  fireEvent.click(screen.getByRole("radio", { name: "Okay" })); expect(change).toHaveBeenCalledWith({ option_id: "ok" });
});
it("supports empty legacy form context and requires explicit v2 draft upgrade", async () => {
  vi.mocked(staffRequest).mockResolvedValue({ version: 4, schema: null }); mount(<ProgrammeFormEditor eventId={42} formKey="registration" />);
  fireEvent.click(await screen.findByRole("button", { name: "Upgrade draft to form v2" })); expect(screen.getByRole("region", { name: "Form builder" })).toBeVisible(); expect(screen.getByLabelText("Question type")).toBeVisible();
});
it("selects next-up authorized events without reviving ended events", () => {
  mount(<NextUpEvents now={new Date("2026-10-18T10:00:00Z")} events={[{ id: 1, title: "Ended", starts_at: "2026-10-17T09:00:00Z", ends_at: "2026-10-17T11:00:00Z", href: "/admin/events?event=1" }, { id: 2, title: "Open workshop", starts_at: "2026-10-18T09:00:00Z", ends_at: "2026-10-18T11:00:00Z", href: "/admin/events?event=2" }]} />);
  expect(screen.queryByText("Ended")).not.toBeInTheDocument(); expect(screen.getByText("Happening now")).toBeVisible(); expect(screen.getByRole("link", { name: "Open event" })).toHaveAttribute("href", "/admin/events?event=2");
});
it("clears form data and local edits when permission is withdrawn during refetch", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.mocked(staffRequest).mockResolvedValue({ version: 1, schema: { schema_version: 2, form_id: "registration", revision: 1, questions: [{ id: "private", type: "short_text", label: "Private question" }] } });
  mount(<ProgrammeFormEditor eventId={42} formKey="registration" />, client);
  fireEvent.change(await screen.findByLabelText("Question label"), { target: { value: "Unsaved private draft" } });
  vi.mocked(staffRequest).mockRejectedValue(new StructuredApiError(403, { detail: "Access withdrawn" }));
  await client.invalidateQueries({ queryKey: ["event-form-v2", 42] });
  expect(await screen.findByRole("alert")).toHaveTextContent("no longer available"); expect(screen.queryByDisplayValue("Unsaved private draft")).not.toBeInTheDocument();
  await waitFor(() => expect(client.getQueryCache().find({ queryKey: ["event-form-v2", 42] })?.state.data).toBeUndefined());
});
