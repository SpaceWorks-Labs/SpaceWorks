import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../../test/axe";
import { StageAnswerFields, StageChecklist, StageTracker } from "./StageTracker";
import type { ParticipantStage } from "./stageRules";
import type { Project } from "./types";


const stage = (rules: Partial<ParticipantStage["rules"]> = {}, extra: Partial<ParticipantStage> = {}): ParticipantStage => ({
  id: 7, position: 1, name: "Prototype", description: "", opens_at: null, deadline: "2026-12-01T10:00:00Z", grace_minutes: 0,
  effective_deadline: "2026-12-01T10:00:00Z", extended: false, status: "open",
  rules: { content_mode: "files_and_links", required_link_kinds: [], min_files: 0, max_files: null, max_links: null,
    accepted_families: [], max_bytes_per_file: null, video_hosts: [], resubmission: "until_deadline", late_policy: "reject", ...rules },
  custom_fields: [], requires_previous: false, shortlist_after: false, shortlist_label: "", submitted: false, snapshot_id: null,
  submitted_at: null, blocked: null, shortlist_status: null, ...extra });

const project: Project = { title: "", tagline: "", problem: "", description: "", challenges: "", tech_tags: [],
  ai_declaration: { used: false, details: "" }, reuse_declaration: { used: false, details: "" }, public_requested: false,
  track_ids: [], prize_ids: [], asset_ids: [], public_asset_ids: [], form_answers: {}, links: [] };

describe("participant stage view", () => {
  it("shows each stage's status, shortlist result and why a stage is blocked", async () => {
    const { container } = render(<StageTracker timezone="UTC" activeId={8} stages={[
      stage({}, { id: 7, name: "Idea", status: "closed", submitted: true, shortlist_after: true, shortlist_status: "shortlisted" }),
      stage({}, { id: 8, position: 2, name: "Prototype", extended: true, feedback: ["Strong idea; narrow the scope."] }),
      stage({}, { id: 9, position: 3, name: "Final", status: "upcoming", blocked: "shortlist_pending" })]} />);
    expect(screen.getByText("Submitted")).toBeTruthy();
    expect(screen.getByText("Shortlist: Shortlisted")).toBeTruthy();
    expect(screen.getByText(/extended for your team/)).toBeTruthy();
    expect(screen.getByText("Feedback from the judges")).toBeTruthy();
    expect(screen.getByText("Strong idea; narrow the scope.")).toBeTruthy();
    expect(screen.getByText("Opens to shortlisted teams once the shortlist is published.")).toBeTruthy();
    expect(screen.getByText("2. Prototype").closest("li")?.getAttribute("aria-current")).toBe("step");
    await expectNoA11yViolations(container);
  });

  it("renders the checklist and stores custom answers under the stage key", () => {
    const s = stage({ min_files: 1 }, { custom_fields: [{ key: "pitch", label: "One-line pitch", type: "short_text", required: true }] });
    render(<StageChecklist stage={s} project={project} />);
    expect(screen.getByText("To do: At least 1 file")).toBeTruthy();
    expect(screen.getByText("To do: Answer: One-line pitch")).toBeTruthy();
    const change = vi.fn();
    render(<StageAnswerFields stage={s} project={project} onChange={change} />);
    fireEvent.change(screen.getByLabelText("One-line pitch (required)"), { target: { value: "Robots for gardens" } });
    expect(change).toHaveBeenCalledWith({ "stage:7": { pitch: "Robots for gardens" } });
  });

  it("says a presentation stage needs nothing uploaded", () => {
    render(<StageChecklist stage={stage({ content_mode: "presentation" })} project={project} />);
    expect(screen.getByText(/Nothing to upload/)).toBeTruthy();
  });
});
