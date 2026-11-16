import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EventDuplicateAction } from "./EventDuplicateAction";
import { EventRegistrationAnswers } from "./EventRegistrationAnswers";
import { EventFeedbackPanel } from "./EventFeedbackPanel";
import { offerCancellationUndo } from "./eventToolsApi";
import { clearToasts, toastStore, undoToast } from "../../components/ui/toastStore";
import type { EventRegistration, StaffEvent } from "./eventsApi";
import { StructuredApiError } from "../../lib/api";
import { DetailDrawer } from "../../components/ui";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequest: request }));
vi.mock("./EventFeedbackResponses", () => ({ EventFeedbackResponses: () => null }));

const question = { id: "experience", label: "Experience", type: "short_text" as const, options: [], required: true };
const registration: EventRegistration = { id: 4, event_id: 3, name: "Maker", email: "", phone: "", payment: null,
  created_at: "2026-10-20T10:00:00Z", status: "registered", custom_answers: { version: 1, answers: [{ ...question, value: "Beginner" }] } };
const event = { id: 3, title: "Workshop", series_summary: { title: "Weekly workshop" } } as StaffEvent;
const survey = { id: 9, title: "Review", questions: [question], thank_you_text: "Thanks", certificate_enabled: false, is_open: false, response_count: 0, answered_question_ids: [] };
function show(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  return { invalidate, ...render(<QueryClientProvider client={client}>{node}</QueryClientProvider>) };
}
beforeEach(() => { request.mockReset(); clearToasts(); });

describe("event staff tools", () => {
  it("portals the child dialog outside the drawer that becomes inert", () => {
    show(<DetailDrawer open title="Event drawer" onClose={vi.fn()}><EventDuplicateAction event={event} makerspaceId={7} /></DetailDrawer>);
    const drawer = screen.getByRole("dialog", { name: "Event drawer" });
    fireEvent.click(screen.getByRole("button", { name: "Duplicate event" }));
    const dialog = screen.getByRole("dialog", { name: "Duplicate event" });
    expect(drawer.contains(dialog)).toBe(false);
    expect(dialog.closest("[inert]")).toBeNull();
    expect(screen.getByRole("button", { name: "Create draft copy" })).toBeEnabled();
  });
  it("duplicates standalone by default and refreshes accessible event lists", async () => {
    request.mockResolvedValue({ id: 10, title: "Workshop (copy)" });
    const { invalidate } = show(<EventDuplicateAction event={event} makerspaceId={7} />);
    fireEvent.click(screen.getByRole("button", { name: "Duplicate event" }));
    expect(screen.getByRole("checkbox")).not.toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Create draft copy" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/events/3/duplicate/", { method: "POST", body: '{"attach_series":false}' }));
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["events", "accessible"] }));
  });

  it("sends an explicit series choice and reports permission refusal", async () => {
    request.mockRejectedValue(new StructuredApiError(403, { detail: "Series management permission is required." }));
    show(<EventDuplicateAction event={event} makerspaceId={7} />);
    fireEvent.click(screen.getByRole("button", { name: "Duplicate event" }));
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Create draft copy" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Series management permission is required.");
    expect(request).toHaveBeenCalledWith("/admin/events/3/duplicate/", { method: "POST", body: '{"attach_series":true}' });
  });

  it("prefills answer snapshots, validates required answers and uses the existing roster identity", async () => {
    request.mockResolvedValue(registration);
    const { invalidate } = show(<EventRegistrationAnswers row={registration} schema={[question]} makerspaceId={7} eventId={3} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit answers" }));
    const input = screen.getByRole("textbox", { name: /Experience/ });
    expect(input).toHaveValue("Beginner");
    fireEvent.change(input, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save answers" }));
    expect(screen.getByText("This question is required.")).toBeVisible(); expect(request).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: "Intermediate" } });
    fireEvent.click(screen.getByRole("button", { name: "Save answers" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/event-registrations/4/answers/", { method: "PATCH", body: '{"custom_answers":{"experience":"Intermediate"}}' }));
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["event", 3, "registrations"] }));
  });

  it("applies a selected feedback template and displays its questions", async () => {
    request.mockImplementation((_, options) => options?.method === "POST" ? Promise.resolve({ ...survey, title: "Session review", questions: [{ ...question, label: "Speaker feedback" }] }) : Promise.resolve({ survey }));
    show(<EventFeedbackPanel eventId={3} makerspaceId={7} canViewResponses={false} />);
    await screen.findByDisplayValue("Review");
    fireEvent.change(screen.getByLabelText("Feedback template"), { target: { value: "session_speaker" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply template" }));
    await screen.findByDisplayValue("Session review");
    expect(request).toHaveBeenCalledWith("/admin/events/3/feedback-survey/templates/", { method: "POST", body: '{"template":"session_speaker"}' });
    expect(screen.getByDisplayValue("Speaker feedback")).toBeVisible();
  });

  it("does not offer replacement templates after a survey response", async () => {
    request.mockResolvedValue({ survey: { ...survey, response_count: 1, answered_question_ids: ["experience"] } });
    show(<EventFeedbackPanel eventId={3} makerspaceId={7} canViewResponses={false} />);
    await screen.findByDisplayValue("Review");
    expect(screen.getByLabelText("Feedback template")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Apply template" })).toBeDisabled();
  });
});

describe("cancellation undo", () => {
  it("uses the server deadline and reports an admission refusal without hiding it", async () => {
    const restore = vi.fn().mockRejectedValue(new Error("A place is no longer available."));
    offerCancellationUndo({ ...registration, restore_until: new Date(Date.now() + 60_000).toISOString() }, restore);
    const row = toastStore.snapshot()[0]; expect(row.undo).toBeDefined();
    await undoToast(row.id);
    expect(restore).toHaveBeenCalledWith(4);
    expect(toastStore.snapshot()[0].message).toContain("A place is no longer available.");
    expect(toastStore.snapshot()[0].undo).toBeUndefined();
  });
  it("offers no undo without eligible server provenance or after expiry", () => {
    offerCancellationUndo({ ...registration, restore_until: null }, vi.fn());
    offerCancellationUndo({ ...registration, restore_until: new Date(Date.now() - 1).toISOString() }, vi.fn());
    expect(toastStore.snapshot().every((row) => !row.undo)).toBe(true);
  });
  it("expires the undo toast after the remaining five-minute window", () => {
    vi.useFakeTimers();
    try {
      offerCancellationUndo({ ...registration, restore_until: new Date(Date.now() + 300_000).toISOString() }, vi.fn());
      vi.advanceTimersByTime(299_999); expect(toastStore.snapshot()[0].undo).toBeDefined();
      vi.advanceTimersByTime(1); expect(toastStore.snapshot()).toEqual([]);
    } finally { clearToasts(); vi.useRealTimers(); }
  });
});
