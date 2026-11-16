import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { staffRequest } from "../../../lib/api";
import { StructuredApiError } from "../../../lib/api/errors";
import { BroadcastComposer } from "./BroadcastComposer";
import { BroadcastUndoBar } from "./BroadcastUndoBar";
import { EventAnalyticsExtras } from "./EventAnalyticsExtras";
import { IntegrityFlag } from "../hackathonJudging/IntegrityFlag";
import { MentorAlertRooms } from "../mentorDesk/MentorAlertRooms";
import type { BroadcastCampaign } from "./broadcastApi";

vi.mock("../../../lib/api", async importOriginal => ({ ...await importOriginal<typeof import("../../../lib/api")>(), staffRequest: vi.fn() }));
const notFound = () => new StructuredApiError(404, { detail: "Not found." });
const draft: BroadcastCampaign = { id: 7, version: 3, subject: "Hello", body: "Body", statuses: ["registered"], attendance: "any", status: "draft", available_at: null, render_schema_version: 2, design: "classic", ctas: [] };
function mount(element: React.ReactNode) { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{element}</QueryClientProvider>); }
beforeEach(() => { vi.mocked(staffRequest).mockReset(); });
afterEach(() => { vi.useRealTimers(); });

it("hides templates and the newer designs while the switch is off", async () => {
  vi.mocked(staffRequest).mockImplementation(async path => { if (String(path).includes("broadcast-templates")) throw notFound(); return draft; });
  mount(<BroadcastComposer eventId={1} makerspaceId={2} onSaved={() => {}} />);
  await waitFor(() => expect(staffRequest).toHaveBeenCalled());
  expect(screen.queryByText("Start from a template")).not.toBeInTheDocument();
  expect(screen.getByRole("radio", { name: /Classic/ })).toBeInTheDocument();
  expect(screen.queryByRole("radio", { name: /Letter/ })).not.toBeInTheDocument();
});

it("shows the gallery and all six designs while on, and a template fills the draft", async () => {
  vi.mocked(staffRequest).mockImplementation(async path => String(path).includes("broadcast-templates")
    ? [{ key: "thanks", label: "Thanks for coming", description: "After", subject: "Thank you", body: "Hi {{ name }}", statuses: ["attended"], attendance: "attended", design: "letter" }] : draft);
  mount(<BroadcastComposer eventId={1} makerspaceId={2} onSaved={() => {}} />);
  fireEvent.click(await screen.findByRole("button", { name: /Thanks for coming/ }));
  expect(screen.getByLabelText("Subject")).toHaveValue("Thank you");
  expect(screen.getByRole("radio", { name: /Letter/ })).toBeChecked();
});

it("autosaves an existing draft with its version and reports a stale tab", async () => {
  vi.mocked(staffRequest).mockImplementation(async (path, options) => {
    if (String(path).includes("broadcast-templates")) throw notFound();
    if (options?.method === "PATCH") throw new StructuredApiError(409, { detail: "Stale." });
    return draft;
  });
  mount(<BroadcastComposer eventId={1} makerspaceId={2} existing={draft} onSaved={() => {}} />);
  fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Hello again" } });
  await waitFor(() => expect(vi.mocked(staffRequest).mock.calls.some(([, options]) => options?.method === "PATCH")).toBe(true), { timeout: 4000 });
  const call = vi.mocked(staffRequest).mock.calls.find(([, options]) => options?.method === "PATCH")!;
  expect(call[0]).toBe("/admin/events/1/broadcasts/7/");
  expect(JSON.parse(String(call[1]?.body))).toMatchObject({ expected_version: 3, draft: { subject: "Hello again" } });
  expect(await screen.findByText(/changed in another tab/)).toBeVisible();
});

it("counts the five-second hold down and undoes on click", () => {
  vi.useFakeTimers();
  const undo = vi.fn();
  render(<BroadcastUndoBar until={new Date(Date.now() + 5000).toISOString()} busy={false} onUndo={undo} />);
  expect(screen.getByText("5")).toBeInTheDocument();
  const tick = (ms: number) => { for (let elapsed = 0; elapsed < ms; elapsed += 250) act(() => { vi.advanceTimersByTime(250); }); };
  tick(2100);
  expect(screen.getByText("3")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Undo send/ }));
  expect(undo).toHaveBeenCalled();
  tick(4000);
  expect(screen.getByText(/can no longer be recalled/)).toBeInTheDocument();
});

it("analytics extras state every chart in text and never show free text", async () => {
  vi.mocked(staffRequest).mockResolvedValue({ event_id: 1, timezone_name: "UTC", window_minutes: 15,
    arrivals: [{ window_start: "2026-10-30T09:00:00Z", count: 4 }, { window_start: "2026-10-30T09:15:00Z", count: 9 }],
    checkin_methods: [{ method: "qr", count: 13 }],
    answers: [{ question_id: "q1", label: "Venue", type: "single_choice", answers: [{ label: "Good", count: 3 }], total: 3 }],
    waitlist: { ever_waitlisted: 4, promoted: 3, still_waiting: 1, conversion_percent: 75 }, series: [], short_link_visits: null });
  mount(<EventAnalyticsExtras eventId={1} makerspaceId={2} />);
  expect(await screen.findByText(/13 people checked in/)).toBeVisible();
  expect(screen.getByText(/written answers never are/)).toBeVisible();
  expect(screen.getByText("75%")).toBeVisible();
  expect(screen.queryByText(/Short link/)).not.toBeInTheDocument();
});

it("the integrity chip is information only and absent while off", async () => {
  const scope = { makerspaceId: 2, eventId: 1, actorId: 3, context: "staff" };
  vi.mocked(staffRequest).mockRejectedValueOnce(notFound());
  const { unmount } = mount(<IntegrityFlag scope={scope} snapshotIds={[5]} />);
  await waitFor(() => expect(staffRequest).toHaveBeenCalled());
  expect(screen.queryByLabelText("Integrity information")).not.toBeInTheDocument();
  unmount();
  vi.mocked(staffRequest).mockResolvedValue({ results: [{ snapshot_id: 5, submission_id: 9, rule_keys: ["github_commit_before_kickoff"] }] });
  mount(<IntegrityFlag scope={scope} snapshotIds={[5]} />);
  expect(await screen.findByText(/commits from before kickoff/)).toBeVisible();
  expect(screen.getByText(/never disqualifies/)).toBeVisible();
});

it("mentor alert rooms are not offered while the switch is off", async () => {
  vi.mocked(staffRequest).mockRejectedValue(notFound());
  mount(<MentorAlertRooms scope={{ eventId: 1, makerspaceId: 2, accountId: 3 }} />);
  await waitFor(() => expect(staffRequest).toHaveBeenCalled());
  expect(screen.queryByText(/Chat alerts for new help requests/)).not.toBeInTheDocument();
});
