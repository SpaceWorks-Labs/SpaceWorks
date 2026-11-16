import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import contract from "../../../../../backend/tests/events/programme/contracts/reimbursement_addon.json";
import { AssignmentActionDialog } from "./AssignmentActionDialog";
import type { ManagedAssignment } from "./types";
const mutate = vi.hoisted(() => vi.fn());
vi.mock("./api", () => ({ stageAdminPath: () => "/admin/events/41/", useAssignmentCommand: () => ({ mutate, isPending: false }) }));
const scope = { actorId: 1, makerspaceId: 2, eventId: 41 };
const assignment: ManagedAssignment = { id: 7, stage_form_id: 11, title: "Checklist", version: 3, state: "completed", response_id: 111, response_version: 2,
  stage_form_version: 4, pinned_form_revision_id: 71, opens_at: "2026-12-01T00:00:00Z", due_at: "2026-12-02T00:00:00Z", due_revision: 1,
  required: true, blocked_actions: ["check_in"], allowed_actions: ["cancel", "reassign"], owner_label: "Maker", submitted_revisions: [1], current_submitted_revision: 1,
  organizer_detail_available: true, finance_detail_available: false, published_revisions: [{ id: 72, revision: 2, published_at: "2026-10-01T00:00:00Z" }] };
afterEach(() => { vi.restoreAllMocks(); mutate.mockReset(); });
describe("assignment recovery commands", () => {
  it("requires confirmation and sends every frozen cancel dependency", () => {
    render(<AssignmentActionDialog scope={scope} assignment={assignment} action="cancel" onClose={() => undefined} />);
    expect(screen.getByRole("button", { name: "Confirm cancel" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reason for participant"), { target: { value: "Checklist cancelled." } });
    fireEvent.click(screen.getByRole("checkbox")); fireEvent.submit(screen.getByRole("button", { name: "Confirm cancel" }).closest("form")!);
    const { operation_id: _operation, ...expected } = contract.stages.cancel.body;
    expect(mutate).toHaveBeenCalledWith({ path: "/admin/events/41/stage-assignments/7/cancel/", body: expected }, expect.anything());
  });
  it("shows only published replacements and preserves the UTC reassign vector", () => {
    vi.spyOn(Date, "now").mockReturnValue(Date.parse("2026-10-18T00:00:00Z"));
    render(<AssignmentActionDialog scope={scope} assignment={assignment} action="reassign" onClose={() => undefined} />);
    fireEvent.change(screen.getByLabelText("Published replacement revision"), { target: { value: "72" } });
    const target = new Date(contract.stages.reassign.body.due_at);
    const local = new Date(target.getTime() - target.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    fireEvent.change(screen.getByLabelText("New deadline (your local time)"), { target: { value: local } });
    fireEvent.change(screen.getByLabelText("Reason for participant"), { target: { value: "Use the corrected checklist." } });
    fireEvent.click(screen.getByRole("checkbox")); fireEvent.submit(screen.getByRole("button", { name: "Confirm reassign" }).closest("form")!);
    const { operation_id: _operation, ...expected } = contract.stages.reassign.body;
    expect(mutate).toHaveBeenCalledWith({ path: "/admin/events/41/stage-assignments/7/reassign/", body: expected }, expect.anything());
    expect(screen.getByText(/empty draft/i)).toBeInTheDocument();
  });
});
