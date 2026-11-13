import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../../lib/api";
import { ClaimFinanceAction } from "./ClaimFinanceAction";
import type { ClaimReviewDetail } from "./types";

const mocked = vi.hoisted(() => ({ mutate: vi.fn(), pending: false, error: null as unknown }));
vi.mock("./api", () => ({ reimbursementAdminPath: () => "/admin/events/41/reimbursements/",
  useClaimReviewCommand: () => ({ mutate: mocked.mutate, isPending: mocked.pending, isSuccess: false, error: mocked.error }) }));

const scope = { actorId: 1, makerspaceId: 2, eventId: 41 };
const detail = (over: Partial<ClaimReviewDetail> = {}): ClaimReviewDetail => ({ id: 9, uuid: "claim-uuid", version: 3, state: "submitted", owner_label: "Maker", currency: "INR", claimed_minor: 175000,
  due_at: "2026-12-10T00:00:00Z", due_revision: 1, allowed_actions: [], claim_revision_id: 7, decision_sequence: 0, obligation_version: null, eligibility_revision: 2, attendance_revision: 5,
  registration_id: 101, accepted_cap_minor: 150000, pool_version: 4,
  lines: [{ line_uuid: "rail-line", category: "rail", original_amount_minor: 175000, original_currency: "INR", converted_minor: 175000, receipt_present: true, duplicate_receipt: false, receipt_asset_id: 91, receipt_use_version: 2 },
    { line_uuid: "bus-line", category: "bus", original_amount_minor: 5000, original_currency: "INR", converted_minor: 5000, receipt_present: true, duplicate_receipt: false, receipt_asset_id: 92, receipt_use_version: 3 }],
  attendance_eligible: true, recommendations: [], decision_reason: "", appeal_statement: null, ...over });

function show(action: Parameters<typeof ClaimFinanceAction>[0]["action"], row: ClaimReviewDetail = detail()) {
  const onClose = vi.fn();
  render(<ClaimFinanceAction scope={scope} row={row} action={action} onClose={onClose} />);
  return { onClose };
}
const submit = () => fireEvent.submit(screen.getByRole("button", { name: /Confirm and record|Recording…/ }).closest("form")!);
const fill = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const lastCall = () => mocked.mutate.mock.calls[mocked.mutate.mock.calls.length - 1];
const future = () => { const d = new Date(Date.now() + 7 * 864e5); d.setSeconds(0, 0); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); };

beforeEach(() => { mocked.mutate.mockReset(); mocked.pending = false; mocked.error = null; });
afterEach(() => vi.restoreAllMocks());

describe("extend deadline", () => {
  it("titles the dialog and posts the new UTC due time pinned to the claim and due revisions", () => {
    show("extend");
    expect(screen.getByRole("heading", { name: "Extend claim deadline" })).toBeInTheDocument();
    fill("New due time (your local time)", future());
    fill("Reason", "deadline_extension");
    fill("Finance note", "  Illness  ");
    submit();
    const [call] = lastCall();
    expect(call.path).toBe("/admin/events/41/reimbursements/claims/9/extend/");
    expect(call.body).toMatchObject({ expected_version: 3, due_revision: 1, reason_code: "deadline_extension", note: "Illness" });
    expect(call.body.due_at).toMatch(/Z$/);
  });
  it("refuses a past deadline and does not call the server", () => {
    show("extend");
    fill("New due time (your local time)", "2020-01-01T10:00");
    fill("Reason", "deadline_extension"); fill("Finance note", "x");
    submit();
    expect(screen.getByRole("alert")).toHaveTextContent("Choose a future deadline.");
    expect(mocked.mutate).not.toHaveBeenCalled();
  });
  it("refuses an empty time with a date message", () => {
    show("extend");
    fireEvent.submit(screen.getByRole("button", { name: "Confirm and record" }).closest("form")!);
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a valid date and time.");
  });
  it("closes when the command succeeds", () => {
    const { onClose } = show("extend");
    fill("New due time (your local time)", future()); fill("Reason", "deadline_extension"); fill("Finance note", "ok");
    submit();
    lastCall()[1].onSuccess();
    expect(onClose).toHaveBeenCalled();
  });
});

describe("attendance attestation", () => {
  it("posts the registration, attendance revision, time and trimmed evidence references", () => {
    show("attendance-attestations");
    expect(screen.getByRole("heading", { name: "Exceptional attendance attestation" })).toBeInTheDocument();
    fill("Attended at (your local time)", "2026-11-01T10:00");
    fill("Venue evidence references", " door:1, badge_2 ,, scan-3 ");
    fill("Reason", "attendance_exception"); fill("Finance note", "Seen on CCTV");
    submit();
    const [call] = lastCall();
    expect(call.path).toBe("/admin/events/41/reimbursements/claims/9/attendance-attestations/");
    expect(call.body).toMatchObject({ registration_id: 101, expected_attendance_revision: 5, venue_evidence_refs: ["door:1", "badge_2", "scan-3"], reason_code: "attendance_exception", note: "Seen on CCTV" });
    expect(call.body.attended_at).toMatch(/Z$/);
  });
  it.each([
    ["no references", " , "],
    ["an invalid character", "bad ref!"],
    ["more than 20 references", Array.from({ length: 21 }, (_, i) => `r${i}`).join(",")],
    ["a reference longer than 128 characters", "a".repeat(129)],
  ])("rejects %s", (_name, evidence) => {
    show("attendance-attestations");
    fill("Attended at (your local time)", "2026-11-01T10:00"); fill("Venue evidence references", evidence);
    fill("Reason", "attendance_exception"); fill("Finance note", "x");
    submit();
    expect(screen.getByRole("alert")).toHaveTextContent("Enter up to 20 evidence references (letters, digits, colon, dash or underscore).");
    expect(mocked.mutate).not.toHaveBeenCalled();
  });
  it("refuses a claim with no registration", () => {
    show("attendance-attestations", detail({ registration_id: null }));
    fill("Attended at (your local time)", "2026-11-01T10:00"); fill("Venue evidence references", "door:1");
    fill("Reason", "attendance_exception"); fill("Finance note", "x");
    submit();
    expect(screen.getByRole("alert")).toHaveTextContent("This claim has no registration to attest.");
    expect(mocked.mutate).not.toHaveBeenCalled();
  });
});

describe("receipt allocation override", () => {
  it("lets the finance reviewer pick the receipt line and shows no time field", () => {
    show("receipt-allocation-overrides");
    expect(screen.getByRole("heading", { name: "Receipt allocation override" })).toBeInTheDocument();
    expect(screen.queryByLabelText("New due time (your local time)")).toBeNull();
    expect(screen.getByLabelText("Receipt from claim expense")).toHaveValue("rail-line");
    expect(screen.getByLabelText("Full receipt total (INR)")).toBeInTheDocument();
  });
  it("adds an allocation seeded with the claim and line, edits it, and posts asset, use version, total and allocations", () => {
    show("receipt-allocation-overrides");
    fill("Full receipt total (INR)", "1750");
    fireEvent.click(screen.getByRole("button", { name: "Add allocation" }));
    fill("Claim UUID for allocation 1", "other-claim");
    fill("Line UUID for allocation 1", "other-line");
    fill("Original amount for allocation 1 (INR)", "500");
    fill("Reason", "receipt_shared"); fill("Finance note", "Shared receipt");
    submit();
    const [call] = lastCall();
    expect(call.path).toBe("/admin/events/41/reimbursements/claims/9/receipt-allocation-overrides/");
    expect(call.body).toMatchObject({ asset_id: 91, expected_receipt_use_version: 2, receipt_total_minor: 175000, original_currency: "INR", reason_code: "receipt_shared",
      allocations: [{ claim_uuid: "other-claim", line_uuid: "other-line", original_amount_minor: 50000 }] });
  });
  it("switching the receipt line clears allocations and uses that line's receipt", () => {
    show("receipt-allocation-overrides");
    fill("Full receipt total (INR)", "50");
    fireEvent.click(screen.getByRole("button", { name: "Add allocation" }));
    fill("Receipt from claim expense", "bus-line");
    expect(screen.queryByLabelText("Claim UUID for allocation 1")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Add allocation" }));
    fill("Reason", "receipt_shared"); fill("Finance note", "x");
    submit();
    expect(lastCall()[0].body).toMatchObject({ asset_id: 92, expected_receipt_use_version: 3, allocations: [{ claim_uuid: "claim-uuid", line_uuid: "bus-line", original_amount_minor: 5000 }] });
  });
  it("removes an allocation", () => {
    show("receipt-allocation-overrides");
    fireEvent.click(screen.getByRole("button", { name: "Add allocation" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove allocation" }));
    expect(screen.queryByLabelText("Claim UUID for allocation 1")).toBeNull();
  });
  it("requires a total and at least one allocation", () => {
    show("receipt-allocation-overrides");
    fill("Reason", "receipt_shared"); fill("Finance note", "x");
    submit();
    expect(screen.getByRole("alert")).toHaveTextContent("Enter the receipt total and allocations.");
    fill("Full receipt total (INR)", "100");
    submit();
    expect(screen.getByRole("alert")).toHaveTextContent("Enter the receipt total and allocations.");
    expect(mocked.mutate).not.toHaveBeenCalled();
  });
  it("does nothing for a line with no receipt (no request, no error)", () => {
    show("receipt-allocation-overrides", detail({ lines: [{ ...detail().lines[0], receipt_asset_id: undefined, receipt_present: false }] }));
    submit();
    expect(mocked.mutate).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("closing and failure", () => {
  it("shows the typed server error", () => {
    mocked.error = new StructuredApiError(409, { detail: "changed", code: "claim_version" });
    show("extend");
    expect(screen.getByRole("alert")).toHaveTextContent("This record changed. Reload and review the current version before trying again.");
  });
  it("shows Recording… and disables the fields while pending", () => {
    mocked.pending = true;
    show("extend");
    expect(screen.getByRole("button", { name: "Recording…" })).toBeInTheDocument();
    expect(screen.getByLabelText("Finance note")).toBeDisabled();
  });
  it("an untouched dialog closes without asking; an edited one asks to discard and respects the answer", () => {
    const confirm = vi.spyOn(window, "confirm");
    const first = show("extend");
    fireEvent.keyDown(document, { key: "Escape" });
    fireEvent.click(screen.getAllByRole("button", { name: /close/i })[0]);
    expect(confirm).not.toHaveBeenCalled();
    expect(first.onClose).toHaveBeenCalled();
  });
  it("keeps an edited dialog open when the discard question is declined, closing when accepted", () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    const { onClose } = show("extend");
    fill("Finance note", "Half-written");
    fireEvent.click(screen.getAllByRole("button", { name: /close/i })[0]);
    expect(confirm).toHaveBeenCalledWith("Discard this unsaved finance action?");
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getAllByRole("button", { name: /close/i })[0]);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
  it("cannot be closed while the command is pending", () => {
    mocked.pending = true;
    const { onClose } = show("extend");
    fireEvent.click(screen.getAllByRole("button", { name: /close/i })[0]);
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe("explanatory text per action", () => {
  it.each([
    ["extend", "The owner will be notified of the new deadline."],
    ["attendance-attestations", "Record evidence of venue attendance for this claim. A later attendance correction invalidates this attestation. Holds need separate review."],
    ["receipt-allocation-overrides", "Allocate the original receipt amount across authorized same-host claim lines. The combined amount cannot exceed the receipt total."],
  ] as const)("%s", (action, text) => {
    show(action);
    expect(screen.getByText(text)).toBeInTheDocument();
  });
  it("shows the attestation time field and the evidence field only for attendance, and the receipt currency from the chosen line", () => {
    show("attendance-attestations");
    expect(screen.getByLabelText("Attended at (your local time)")).toBeInTheDocument();
    expect(screen.getByLabelText("Venue evidence references")).toBeInTheDocument();
    expect(screen.queryByLabelText("Full receipt total (INR)")).toBeNull();
  });
  it("a claim with no lines shows an empty receipt picker and a blank currency", () => {
    show("receipt-allocation-overrides", detail({ lines: [] }));
    expect(screen.getByLabelText("Full receipt total ()")).toBeInTheDocument();
    submit();
    expect(mocked.mutate).not.toHaveBeenCalled();
  });
});
