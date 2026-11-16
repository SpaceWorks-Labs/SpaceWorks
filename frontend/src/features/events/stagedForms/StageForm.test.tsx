import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { StageForm } from "./StageForm";
import type { StageResponse } from "./types";
const mocked = vi.hoisted(() => ({ response: {} as StageResponse, busy: false, mutate: vi.fn() }));
vi.mock("./api", () => ({ stagePath: () => "/member/makerspaces/2/events/41", useStageResponse: () => ({ data: mocked.response }), useStageCommand: () => ({ mutate: mocked.mutate, isPending: false, error: null }) }));
vi.mock("./uploads", () => ({ useFormUploads: () => ({ busy: mocked.busy, upload: vi.fn() }) }));
vi.mock("../../accountSavedDetails/RegistrationSavedDetails", () => ({
  useRegistrationSavedDetails: () => ({ data: { values: { institution: "Saved school" }, saved_detail_versions: { institution: 2 }, save_defaults: { institution: true } } }),
  SaveIntentNotice: () => <p>Private save status</p>, FormSaveIntentsNotice: () => <p>Per-form save status</p>,
}));
const scope = { actorId: 1, makerspaceId: 2, eventId: 41 };
function response(): StageResponse { return { id: 111, version: 2, state: "draft", allowed_actions: ["stage_save", "stage_submit"], event_date_revision: 1, selected_revision: null,
  assignment: { id: 7, stage_form_id: 11, title: "School details", version: 3, state: "open", due_at: "2099-12-10T10:00:00Z", opens_at: "2020-12-01T00:00:00Z", due_revision: 1, required: true,
    pinned_form_revision_id: 72, response_id: 111, response_version: 2, blocked_actions: ["check_in"] }, schema: { schema_version: 2, form_id: "stage-11", revision: 1,
    questions: [{ id: "school", type: "short_text", label: "School", required: true, profile_field_key: "institution" }] }, answers: { answers: [] } }; }
afterEach(() => { mocked.mutate.mockReset(); mocked.busy = false; });
describe("applicant stage editor", () => {
  it("reviews Saved details, sends question maps with both versions, and protects dirty drafts", () => {
    mocked.response = response(); render(<StageForm scope={scope} responseId={111} />);
    fireEvent.click(screen.getByRole("button", { name: "Use saved details for empty answers" }));
    expect(screen.getByRole("textbox", { name: "School" })).toHaveValue("Saved school");
    const event = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(event); expect(event.defaultPrevented).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    expect(mocked.mutate).toHaveBeenCalledWith({ path: "/member/makerspaces/2/events/41/stage-responses/111/", method: "PUT", body: {
      expected_version: 2, expected_assignment_version: 3, form: { schema_version: 2, form_id: "stage-11", revision: 1 }, answers: { school: "Saved school" },
      derivations: {}, save_choices: { institution: true }, saved_detail_versions: { institution: 2 }, event_date_revision: 1,
    } }, expect.anything());
  });
  it("blocks submission while scanner checks are pending and when permission is absent", () => {
    mocked.response = response(); mocked.busy = true;
    const { unmount } = render(<StageForm scope={scope} responseId={111} />);
    expect(screen.getByRole("button", { name: "Submit form" })).toBeDisabled(); unmount();
    mocked.busy = false; mocked.response = { ...response(), allowed_actions: [] };
    render(<StageForm scope={scope} responseId={111} />);
    expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Submit form" })).toBeDisabled();
  });
  it("keeps cancelled assignments read-only and preserves submitted history", () => {
    const row = response(); mocked.response = { ...row, selected_revision: 1, assignment: { ...row.assignment, state: "cancelled" } };
    render(<StageForm scope={scope} responseId={111} />);
    expect(screen.getByText(/read-only/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resubmit form" })).toBeDisabled();
  });
  it("preserves independent per-form Saved-details status after submission", () => {
    mocked.response = response();
    mocked.mutate.mockImplementationOnce((_command, options) => options.onSuccess({ id: 111, version: 3, state: "submitted", form_save_intents: [] }));
    render(<StageForm scope={scope} responseId={111} />);
    fireEvent.click(screen.getByRole("button", { name: "Use saved details for empty answers" }));
    fireEvent.submit(screen.getByRole("button", { name: "Submit form" }).closest("form")!);
    expect(screen.getByText("Per-form save status")).toBeInTheDocument();
  });
});
