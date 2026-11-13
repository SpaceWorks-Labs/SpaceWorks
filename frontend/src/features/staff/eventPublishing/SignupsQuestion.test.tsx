import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PublishingQuestions, publishingSummary, type PublishingAnswers } from "./PublishingQuestions";
import { signupPatch, signupSummary, type SignupAnswers } from "./SignupsQuestion";

const base: PublishingAnswers = { is_public: true, listing: "listed", page_state: "live", registration_audience: "members" };
const signups: SignupAnswers = { capacity: 40, close: "before", lead_minutes: 120, closes_at: "", show_registration_count: true, registration_requires_approval: false };

describe("the sign-ups question (B2)", () => {
  it("asks the fourth question and reports each change", () => {
    const onSignups = vi.fn();
    render(<PublishingQuestions answers={base} published onChange={vi.fn()} signups={signups} onSignupsChange={onSignups} />);
    expect(screen.getByRole("group", { name: "4. How do sign-ups work?" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: /Limit the number of spots/ }));
    expect(onSignups).toHaveBeenLastCalledWith({ capacity: 0 });
    fireEvent.click(screen.getByRole("radio", { name: "At a set time" }));
    expect(onSignups).toHaveBeenLastCalledWith({ close: "at" });
    fireEvent.click(screen.getByRole("checkbox", { name: /Approve each sign-up/ }));
    expect(onSignups).toHaveBeenLastCalledWith({ registration_requires_approval: true });
  });
  it("locks approval once published and leaves the question out without a handler", () => {
    const { rerender } = render(<PublishingQuestions answers={base} published onChange={vi.fn()} signups={signups} onSignupsChange={vi.fn()} approvalLocked />);
    expect(screen.getByRole("checkbox", { name: /Approve each sign-up/ })).toBeDisabled();
    rerender(<PublishingQuestions answers={base} published onChange={vi.fn()} />);
    expect(screen.queryByRole("group", { name: "4. How do sign-ups work?" })).not.toBeInTheDocument();
  });
  it("summarises spots, closing and approval in the one sentence", () => {
    expect(signupSummary(signups)).toBe("40 spots · closes 2 hours before the start · places are confirmed straight away");
    expect(publishingSummary(base, true, { ...signups, capacity: 0, close: "open", registration_requires_approval: true }))
      .toMatch(/unlimited spots · no closing time · you approve each sign-up\.$/);
  });
  it("sends only the event fields that changed", () => {
    expect(signupPatch(signups, signups)).toEqual({});
    expect(signupPatch(signups, { ...signups, capacity: 60 })).toEqual({ capacity: 60 });
    expect(signupPatch(signups, { ...signups, close: "open" })).toEqual({ registration_cutoff_at: null, registration_cutoff_lead_minutes: null });
  });
});
