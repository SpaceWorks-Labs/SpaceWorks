import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api";
import { OfflineCheckInOperator } from "./OfflineCheckInOperator";
import type { OfflineRoster, QueuedCheckIn, SyncResponse } from "./eventCheckInOfflineApi";
import type { OfflineCheckInState } from "./eventCheckInOfflineStore";

// The encrypted store is covered by its own tests; here it is a plain in-memory map keyed by scope.
const { store, record } = vi.hoisted(() => ({ store: new Map<string, unknown>(), record: vi.fn() }));
vi.mock("./eventCheckInOfflineStore", () => ({
  pruneExpiredOfflineStates: async () => undefined,
  loadOfflineState: async (scope: string) => store.get(scope) ?? null,
  saveOfflineRoster: async (scope: string, roster: OfflineRoster) => { const s = { roster, operations: [], conflicts: [], lastSyncedAt: null, badgeReceipts: [] }; store.set(scope, s); return s; },
  queueOfflineCheckIn: async (scope: string, op: QueuedCheckIn) => { const s = store.get(scope) as OfflineCheckInState; const n = { ...s, operations: [...s.operations, op] }; store.set(scope, n); return n; },
  queueBadgeReceipt: async (scope: string, receipt: unknown) => { const s = store.get(scope) as OfflineCheckInState; const n = { ...s, badgeReceipts: [...(s.badgeReceipts ?? []), receipt] }; store.set(scope, n); return n; },
  applySyncResults: async (scope: string, results: Array<{ operation_id: string; outcome: string }>, at: string) => {
    const s = store.get(scope) as OfflineCheckInState;
    const n = { ...s, operations: [], badgeReceipts: [], conflicts: results.filter((r) => r.outcome !== "applied"), lastSyncedAt: at }; store.set(scope, n); return n; },
  wipeOfflineState: async (scope: string) => { store.delete(scope); },
}));
vi.mock("../../components/card-print", () => ({ usePrintReceipts: () => ({ record }) }));
vi.mock("./eventBadges/DeskPrintSheet", () => ({ DeskPrintSheet: ({ badge, onSkip, onPrinted }: { badge: { registration_id: number }; onSkip: () => void; onPrinted: (i: { stock: string; role: string }) => void }) =>
  <div>print sheet for {badge.registration_id}<button type="button" onClick={onSkip}>skip print</button><button type="button" onClick={() => onPrinted({ stock: "a6", role: "attendee" })}>printed</button></div> }));

const SCOPE = "event:9";
const roster = (over: Partial<OfflineRoster> = {}): OfflineRoster => ({
  lease_token: "l", lease_id: "id", server_time: "2026-11-01T00:00:00Z", issued_at: "2026-11-01T00:00:00Z", expires_at: "2999-01-01T00:00:00Z",
  scan_opens_at: "2026-11-01T00:00:00Z", scan_closes_at: "2999-01-01T00:00:00Z", sync_deadline: "2999-01-01T00:00:00Z",
  event: { id: 9, title: "Fest", starts_at: "2026-11-01T00:00:00Z", ends_at: "2999-01-01T00:00:00Z" },
  registrations: [{ registration_id: 1, checkin_token: "TOKEN-ONE", name: "Asha Rao", host_waiver_state: "missing" },
    { registration_id: 2, checkin_token: "TOKEN-TWO", name: "Bo Lee", host_waiver_state: "on_file", badge: { registration_id: 2 } as never }], ...over });
const seed = (over: Partial<OfflineCheckInState> = {}, r: Partial<OfflineRoster> = {}) =>
  store.set(SCOPE, { roster: roster(r), operations: [], conflicts: [], lastSyncedAt: null, badgeReceipts: [], ...over });

type Props = Partial<Parameters<typeof OfflineCheckInOperator>[0]>;
let download: ReturnType<typeof vi.fn>;
let synchronize: ReturnType<typeof vi.fn>;
async function mount(props: Props = {}) {
  const view = render(<OfflineCheckInOperator scope={SCOPE} download={download as never} synchronize={synchronize as never} {...props} />);
  await act(async () => { await Promise.resolve(); });
  return view;
}
async function scan(value: string) {
  fireEvent.click(screen.getByRole("button", { name: "Scan offline" }));
  fireEvent.change(await screen.findByLabelText("Find an offline check-in code"), { target: { value } });
  fireEvent.click(screen.getByRole("button", { name: "Find" }));
}
const setOnline = (value: boolean) => Object.defineProperty(navigator, "onLine", { configurable: true, value });

beforeEach(() => {
  store.clear(); record.mockReset(); setOnline(true);
  download = vi.fn(async () => roster());
  synchronize = vi.fn(async (): Promise<SyncResponse> => ({ recorded_at: "2026-11-02T00:00:00Z", results: [] }));
});
afterEach(() => setOnline(true));

describe("empty and download states", () => {
  it("says nothing is stored and offers Download roster; downloading stores it", async () => {
    await mount();
    expect(screen.getByText("No attendee data is stored on this device.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Wipe attendee data/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Download roster" }));
    expect(await screen.findByRole("button", { name: "Refresh roster" })).toBeInTheDocument();
    expect(download).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/0.*queued · Last sync never/)).toBeInTheDocument();
  });
  it("downloads once automatically when asked to and nothing is stored", async () => {
    await mount({ autoDownload: true });
    await waitFor(() => expect(download).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole("button", { name: "Refresh roster" })).toBeInTheDocument();
  });
  it("does not auto-download when a roster is already stored (regression: it fired before the stored state loaded)", async () => {
    seed();
    await mount({ autoDownload: true });
    expect(await screen.findByRole("button", { name: "Refresh roster" })).toBeInTheDocument();
    expect(download).not.toHaveBeenCalled();
  });
  it.each([400, 403, 410])("a %s from the server wipes the device and shows the message", async (status) => {
    seed();
    download.mockRejectedValueOnce(new StructuredApiError(status, { detail: "Lease revoked", code: "lease_revoked" }));
    await mount();
    fireEvent.click(screen.getByRole("button", { name: "Refresh roster" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Lease revoked");
    expect(store.has(SCOPE)).toBe(false);
    expect(screen.getByText("No attendee data is stored on this device.")).toBeInTheDocument();
  });
  it("keeps stored data on a transient failure and falls back to a generic message for non-errors", async () => {
    seed();
    download.mockRejectedValueOnce(new Error("Network down"));
    await mount();
    fireEvent.click(screen.getByRole("button", { name: "Refresh roster" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Network down");
    expect(store.has(SCOPE)).toBe(true);
    download.mockRejectedValueOnce("weird");
    fireEvent.click(screen.getByRole("button", { name: "Refresh roster" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Could not download roster."));
  });
  it("shows the online/offline wording and follows connection events", async () => {
    await mount();
    expect(screen.getByText("Online · attendee names are encrypted on this device.")).toBeInTheDocument();
    setOnline(false);
    act(() => { window.dispatchEvent(new Event("offline")); });
    expect(screen.getByText("Offline · attendee names are encrypted on this device.")).toBeInTheDocument();
  });
  it("reloads the stored state when the page becomes visible again", async () => {
    await mount();
    seed();
    Object.defineProperty(document, "hidden", { configurable: true, value: false });
    act(() => { document.dispatchEvent(new Event("visibilitychange")); });
    expect(await screen.findByRole("button", { name: "Refresh roster" })).toBeInTheDocument();
  });
});

describe("scanning", () => {
  it("matches a code case-insensitively, shows the person with the waiver state, and cancel clears it", async () => {
    seed();
    await mount();
    await scan("  token-one ");
    expect(await screen.findByText("Asha Rao")).toBeInTheDocument();
    expect(screen.getByText("Waiver: missing")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText("Asha Rao")).toBeNull();
  });
  it("rejects an expired roster before looking anything up", async () => {
    seed({}, { expires_at: "2000-01-01T00:00:00Z" });
    await mount();
    await scan("TOKEN-ONE");
    expect(await screen.findByRole("alert")).toHaveTextContent("The offline roster expired. Download it again.");
  });
  it("refreshes the roster online for a code it does not know, finding someone added later", async () => {
    seed();
    download.mockResolvedValue(roster({ registrations: [{ registration_id: 3, checkin_token: "LATE", name: "Late Comer", host_waiver_state: "on_file" }] }));
    await mount();
    await scan("late");
    expect(await screen.findByText("Late Comer")).toBeInTheDocument();
    expect(download).toHaveBeenCalledTimes(1);
  });
  it("says it is not a code for this event when the refreshed roster has none, and when offline", async () => {
    seed();
    await mount();
    await scan("NOPE");
    expect(await screen.findByRole("alert")).toHaveTextContent("That is not a check-in code for this event.");
    setOnline(false);
    download.mockClear();
    await scan("NOPE2");
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("That is not a check-in code for this event."));
    expect(download).not.toHaveBeenCalled();
  });
  it("tolerates a failed refresh and reports not-a-code", async () => {
    seed();
    download.mockRejectedValue(new Error("boom"));
    await mount();
    await scan("NOPE");
    expect(await screen.findByRole("alert")).toHaveTextContent("That is not a check-in code for this event.");
  });
  it("refuses to refresh the roster while check-ins or receipts are waiting to sync", async () => {
    seed({ operations: [{ operation_id: "o", checkin_token: "TOKEN-ONE", reported_occurred_at: "2026-11-01T00:00:00Z" }] });
    await mount();
    await scan("UNKNOWN");
    expect(await screen.findByRole("alert")).toHaveTextContent("Synchronize first, then refresh the roster to include people added since it was downloaded.");
    expect(download).not.toHaveBeenCalled();
  });
  it("Done closes the scanner", async () => {
    seed();
    await mount();
    fireEvent.click(screen.getByRole("button", { name: "Scan offline" }));
    fireEvent.click(await screen.findByRole("button", { name: "Done" }));
    expect(screen.queryByLabelText("Find an offline check-in code")).toBeNull();
  });
});

describe("confirming attendance", () => {
  it("queues a check-in with a fresh operation id and the person's token", async () => {
    seed();
    await mount();
    await scan("TOKEN-ONE");
    fireEvent.click(await screen.findByRole("button", { name: "Confirm attendance" }));
    await waitFor(() => expect((store.get(SCOPE) as OfflineCheckInState).operations).toHaveLength(1));
    const op = (store.get(SCOPE) as OfflineCheckInState).operations[0];
    expect(op.checkin_token).toBe("TOKEN-ONE");
    expect(op.operation_id).toMatch(/[0-9a-f-]{36}/);
    await waitFor(() => expect(screen.getByText(/Expires/)).toHaveTextContent("· 1 queued"));
    expect(screen.queryByText("Asha Rao")).toBeNull();
    expect(screen.queryByText(/print sheet/)).toBeNull();
  });
  it("is refused once the scan window has closed", async () => {
    seed({}, { scan_closes_at: "2000-01-01T00:00:00Z" });
    await mount();
    await scan("TOKEN-ONE");
    fireEvent.click(await screen.findByRole("button", { name: "Confirm attendance" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The event check-in window has closed.");
    expect((store.get(SCOPE) as OfflineCheckInState).operations).toHaveLength(0);
  });
  it("prints the roster's own badge when the badge desk is on, then queues the receipt", async () => {
    seed({}, { badges: {} as never });
    await mount();
    await scan("TOKEN-TWO");
    fireEvent.click(await screen.findByRole("button", { name: "Confirm attendance" }));
    expect(await screen.findByText("print sheet for 2")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "printed" }));
    expect(record).toHaveBeenCalledWith({ registration_id: 2, method: "offline", stock: "a6", role: "attendee" });
    fireEvent.click(screen.getByRole("button", { name: "skip print" }));
    expect(screen.queryByText(/print sheet/)).toBeNull();
  });
  it("asks the server for a badge the roster lacks, and ignores a missing badge desk", async () => {
    seed({}, { badges: {} as never });
    const fetchBadge = vi.fn().mockResolvedValue({ badge: { registration_id: 1 } });
    await mount({ fetchBadge });
    await scan("TOKEN-ONE");
    fireEvent.click(await screen.findByRole("button", { name: "Confirm attendance" }));
    expect(await screen.findByText("print sheet for 1")).toBeInTheDocument();
    expect(fetchBadge).toHaveBeenCalledWith(1);
  });
  it("skips printing when the online badge lookup fails or returns no badge, and when offline", async () => {
    seed({}, { badges: {} as never });
    const fetchBadge = vi.fn().mockRejectedValue(new Error("no desk"));
    await mount({ fetchBadge });
    await scan("TOKEN-ONE");
    fireEvent.click(await screen.findByRole("button", { name: "Confirm attendance" }));
    await waitFor(() => expect(fetchBadge).toHaveBeenCalled());
    expect(screen.queryByText(/print sheet/)).toBeNull();
    fetchBadge.mockClear(); setOnline(false);
    await scan("TOKEN-TWO");
    fireEvent.click(await screen.findByRole("button", { name: "Confirm attendance" }));
    await screen.findByText("print sheet for 2");
    expect(fetchBadge).not.toHaveBeenCalled();
  });
});

describe("synchronize", () => {
  const queued: QueuedCheckIn = { operation_id: "op-1", checkin_token: "TOKEN-ONE", reported_occurred_at: "2026-11-01T00:00:00Z" };
  it("is disabled with nothing queued, or when offline", async () => {
    seed();
    await mount();
    expect(screen.getByRole("button", { name: "Synchronize" })).toBeDisabled();
    store.clear(); seed({ operations: [queued] });
    setOnline(false);
    act(() => { window.dispatchEvent(new Event("offline")); });
    expect(screen.getByRole("button", { name: "Synchronize" })).toBeDisabled();
  });
  it("sends the roster, operations and receipts, then shows conflicts and calls onSynchronized", async () => {
    seed({ operations: [queued], badgeReceipts: [{ registration_id: 1, method: "offline" } as never] });
    synchronize.mockResolvedValue({ recorded_at: "2026-11-02T00:00:00Z", results: [{ operation_id: "op-1", outcome: "registration_changed" }] });
    const onSynchronized = vi.fn();
    await mount({ onSynchronized });
    fireEvent.click(screen.getByRole("button", { name: "Synchronize" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("1 synchronization conflicts");
    expect(screen.getByText("Registration changed since the roster was downloaded")).toBeInTheDocument();
    expect(synchronize.mock.calls[0][1]).toEqual([queued]);
    expect(synchronize.mock.calls[0][2]).toHaveLength(1);
    expect(onSynchronized).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/Last sync/)).not.toHaveTextContent("never");
  });
  it.each([400, 403, 410])("a %s on sync wipes the device", async (status) => {
    seed({ operations: [queued] });
    synchronize.mockRejectedValue(new StructuredApiError(status, { detail: "Lease expired", code: "lease_expired" }));
    await mount();
    fireEvent.click(screen.getByRole("button", { name: "Synchronize" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Lease expired");
    expect(store.has(SCOPE)).toBe(false);
  });
  it("keeps queued check-ins on a transient failure, with a generic fallback message", async () => {
    seed({ operations: [queued] });
    synchronize.mockRejectedValueOnce(new Error("Gateway timeout")).mockRejectedValueOnce(0);
    await mount();
    fireEvent.click(screen.getByRole("button", { name: "Synchronize" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Gateway timeout");
    expect(store.has(SCOPE)).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Synchronize" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Could not synchronize check-ins."));
  });
});

describe("wipe", () => {
  it("removes attendee data only after confirmation", async () => {
    seed();
    await mount();
    fireEvent.click(screen.getByRole("button", { name: "Wipe attendee data…" }));
    expect(await screen.findByText("Wipe attendee data from this device?")).toBeInTheDocument();
    expect(store.has(SCOPE)).toBe(true);
    const confirm = screen.getByRole("button", { name: "Wipe attendee data" });
    fireEvent.click(confirm);
    await waitFor(() => expect(store.has(SCOPE)).toBe(false));
    expect(await screen.findByText("No attendee data is stored on this device.")).toBeInTheDocument();
  });
});
