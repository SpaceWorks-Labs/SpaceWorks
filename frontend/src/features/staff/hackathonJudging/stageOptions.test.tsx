import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { staffRequest } from "../../../lib/api";
import { RequiredSubmissionField } from "../eventReimbursements/RequiredSubmissionField";
import type { PolicySettings } from "../eventReimbursements/types";
import { ProgrammeOptionsPanel } from "./ProgrammeOptionsPanel";
import { RoundStageField } from "./RoundStageField";

vi.mock("../../../lib/api", async original => ({ ...await original<typeof import("../../../lib/api")>(), staffRequest: vi.fn() }));

const options = { id: 1, event_id: 42, version: 3, allowed_actions: [], currency: "inr", results_email: false, submission_receipt_email: false,
  finalists_email: false, refund_on_disqualification: false, entry_fee: "200.00", team_fee: null, results_email_sent: false,
  published_result_version: null, stage_reminder_email: false, shortlist_email: false, entry_fee_stage: 1 };
const plan = { stages: [{ id: 7, position: 1, name: "Idea" }, { id: 8, position: 2, name: "Final" }] };

function wrap(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

describe("stage controls for staff", () => {
  it("saves the stage email switches and the entry fee stage", async () => {
    vi.mocked(staffRequest).mockReset().mockImplementation(async path => (String(path).includes("submission-stages") ? plan : options) as never);
    wrap(<ProgrammeOptionsPanel scope={{ eventId: 42, makerspaceId: 1, actorId: 2, context: "person" }} entryFees paidTeams={false} />);
    fireEvent.click(await screen.findByLabelText("Email teams whether they were shortlisted when a stage shortlist is published"));
    await waitFor(() => expect(vi.mocked(staffRequest).mock.calls.some(([, o]) => o?.method === "PATCH")).toBe(true));
    const patch = JSON.parse(String(vi.mocked(staffRequest).mock.calls.find(([, o]) => o?.method === "PATCH")![1]?.body));
    expect(patch).toMatchObject({ shortlist_email: true, expected_version: 3 });
    expect(screen.getByLabelText("Remind teams 24 hours before each submission stage deadline")).toBeTruthy();
    fireEvent.change(await screen.findByLabelText("Entry fee is due before"), { target: { value: "2" } });
    await waitFor(() => expect(vi.mocked(staffRequest).mock.calls.filter(([, o]) => o?.method === "PATCH").length).toBe(2));
    const second = JSON.parse(String(vi.mocked(staffRequest).mock.calls.filter(([, o]) => o?.method === "PATCH")[1][1]?.body));
    expect(second).toMatchObject({ entry_fee_stage: 2 });
  });

  it("lets a round pick its stage and freezes the choice once open", async () => {
    vi.mocked(staffRequest).mockReset().mockImplementation(async () => plan as never);
    const change = vi.fn();
    const { rerender } = wrap(<RoundStageField eventId={42} value="" onChange={change} locked={false} />);
    fireEvent.change(await screen.findByLabelText("Stage this round judges"), { target: { value: "7" } });
    expect(change).toHaveBeenCalledWith("7");
    rerender(<QueryClientProvider client={new QueryClient()}><RoundStageField eventId={42} value="7" onChange={change} locked /></QueryClientProvider>);
    expect((await screen.findByLabelText("Stage this round judges") as HTMLSelectElement).disabled).toBe(true);
  });

  it("maps the reimbursement rule and keeps the yes/no mirror in step (G11)", () => {
    const seen: PolicySettings[] = [];
    function Harness() {
      const [value, setValue] = useState({ require_project_submission: true } as PolicySettings);
      return <RequiredSubmissionField value={value} onChange={next => { seen.push(next); setValue(next); }} />;
    }
    render(<Harness />);
    const select = screen.getByLabelText("Project submission required") as HTMLSelectElement;
    expect(select.value).toBe("any_stage");
    fireEvent.change(select, { target: { value: "shortlisted_at" } });
    expect(seen.at(-1)).toMatchObject({ required_submission: "shortlisted_at", required_submission_stage: 1, require_project_submission: true });
    fireEvent.change(screen.getByLabelText("Stage position"), { target: { value: "2" } });
    expect(seen.at(-1)).toMatchObject({ required_submission_stage: 2 });
    fireEvent.change(select, { target: { value: "none" } });
    expect(seen.at(-1)).toMatchObject({ required_submission: "none", required_submission_stage: null, require_project_submission: false });
  });
});
