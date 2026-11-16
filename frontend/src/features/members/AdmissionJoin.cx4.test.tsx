import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { AdmissionJoin } from "./AdmissionJoin";
import type { PublicAdmission } from "./membershipAdmissionApi";

const settings: PublicAdmission = { join_mode: "open", vouches_required: 0, payment_timing: "before_activation",
  application_schema: [{ id: "purpose", label: "What will you make?", type: "short_text", options: [], required: true }],
  default_plan: { id: 1, name: "Community", amount: "10.00", currency: "usd" }, joining_fee: "5.00" };

describe("admission pending, refusal and switch states", () => {
  it("blocks duplicate submission while the server mutation is pending", () => {
    const onJoin = vi.fn();
    render(<AdmissionJoin settings={settings} signedIn pending onJoin={onJoin} onSignIn={vi.fn()} />);
    const sending = screen.getByRole("button", { name: "Sending…" });
    expect(sending).toBeDisabled();
    fireEvent.click(sending);
    expect(onJoin).not.toHaveBeenCalled();
  });

  it.each([
    [403, "permission_denied", "Membership is not available to you."],
    [404, "module_disabled", "Membership is turned off."],
    [503, "temporarily_unavailable", "Please try again."],
  ])("announces a %s refusal without losing the application fields", (status, code, detail) => {
    const onJoin = vi.fn();
    const props = { settings, signedIn: true, pending: false, onJoin, onSignIn: vi.fn() };
    const view = render(<AdmissionJoin {...props} />);
    fireEvent.change(screen.getByRole("textbox", { name: /What will you make/ }), {
      target: { value: "A community weather station" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply to join" }));
    expect(onJoin).toHaveBeenCalledExactlyOnceWith({ purpose: "A community weather station" }, {});
    view.rerender(<AdmissionJoin {...props} error={new StructuredApiError(status, { code, detail })} />);
    expect(screen.getByRole("alert")).toHaveTextContent(detail);
    expect(screen.getByRole("textbox", { name: /What will you make/ })).toHaveValue("A community weather station");
    expect(screen.getByRole("button", { name: "Apply to join" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Apply to join" }));
    expect(onJoin).toHaveBeenCalledTimes(2);
    expect(onJoin).toHaveBeenNthCalledWith(2, { purpose: "A community weather station" }, {});
  });

  it("charges off hides all fee copy and restores it when the capability is enabled", () => {
    const props = { settings, signedIn: true, pending: false, onJoin: vi.fn(), onSignIn: vi.fn() };
    const view = render(<AdmissionJoin {...props} showPrice={false} />);
    expect(screen.getByText("Plan: Community")).toBeVisible();
    expect(screen.queryByText(/Joining fee:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Payment is required/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Join instantly" })).toBeEnabled();
    view.rerender(<AdmissionJoin {...props} showPrice />);
    expect(screen.getByText("Plan: Community · $10.00")).toBeVisible();
    expect(screen.getByText("Joining fee: $5.00")).toBeVisible();
    expect(screen.getByRole("button", { name: "Apply to join" })).toBeEnabled();
  });

  it("submits the form from its focusable submit control and clears a prior error on retry", () => {
    const onJoin = vi.fn();
    const props = { settings: { ...settings, application_schema: [] }, signedIn: true, pending: false,
      onJoin, onSignIn: vi.fn() };
    const view = render(<AdmissionJoin {...props} error={new Error("Temporary failure")} />);
    const submit = screen.getByRole("button", { name: "Apply to join" });
    submit.focus();
    expect(submit).toHaveFocus();
    expect(submit).toHaveAttribute("type", "submit");
    fireEvent.submit(submit.closest("form")!);
    expect(onJoin).toHaveBeenCalledExactlyOnceWith({}, {});
    view.rerender(<AdmissionJoin {...props} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
