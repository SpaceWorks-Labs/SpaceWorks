import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MfaFlow } from "./MfaFlow";
import { mfaRequest, type MfaChallenge } from "./mfaApi";

vi.mock("./mfaApi", () => ({ mfaRequest: vi.fn() }));
const request = vi.mocked(mfaRequest);
const challenge: MfaChallenge = { mfa_required: true, enrollment_required: false, challenge: "first-factor-proof", expires_in: 300 };
function mount(enrolling = false) {
  const complete = vi.fn();
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
    <MfaFlow challenge={{ ...challenge, enrollment_required: enrolling }} onComplete={complete} onCancel={vi.fn()} />
  </QueryClientProvider>);
  return complete;
}

describe("MFA sign-in", () => {
  beforeEach(() => {
    request.mockReset();
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: vi.fn().mockResolvedValue(undefined) } });
  });
  it("does not finish sign-in after a rejected second factor", async () => {
    request.mockRejectedValue(new Error("Invalid or expired MFA challenge."));
    const complete = mount();
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1, name: "Enter your 6-digit code" })).toBeVisible();
    fireEvent.change(screen.getByLabelText("Authenticator or recovery code"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid or expired");
    expect(complete).not.toHaveBeenCalled();
    expect(request).toHaveBeenCalledWith("/auth/mfa/verify", { challenge: challenge.challenge, code: "123456" });
  });

  it("shows QR and manual key, then waits for recovery-code acknowledgement", async () => {
    request.mockResolvedValueOnce({ secret: "MANUALKEY", provisioning_uri: "otpauth://totp/SpaceWorks", qr_data_url: "data:image/png;base64,abc" });
    const result = { access: "verified-access", surface: "staff", user: {}, recovery_codes: ["saved-once-code"] };
    request.mockResolvedValueOnce(result);
    const complete = mount(true);
    expect(screen.getByRole("heading", { level: 1, name: "Set up two-step sign-in" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Show enrollment QR and key" }));
    expect(await screen.findByText("MANUALKEY")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Can't scan? Enter this key"));
    fireEvent.click(screen.getByRole("button", { name: "Copy key" }));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith("MANUALKEY"));
    expect(screen.getByAltText("Scan to add SpaceWorks to your authenticator")).toHaveAttribute("src", "data:image/png;base64,abc");
    fireEvent.change(screen.getByLabelText("Authenticator code"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    expect(await screen.findByText("saved-once-code")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Save your recovery codes" })).toBeVisible();
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(complete).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Copy all codes" }));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith("saved-once-code"));
    expect(screen.getByRole("link", { name: "Download codes" })).toHaveAttribute("download", "space-works-recovery-codes.txt");
    fireEvent.click(screen.getByRole("button", { name: "I saved my codes. Continue" }));
    await waitFor(() => expect(complete).toHaveBeenCalledWith(result));
  });

  it("accepts a recovery code without exposing enrollment controls", async () => {
    request.mockResolvedValue({ access: "verified-access", surface: "member", user: {} });
    const complete = mount();
    expect(screen.queryByText("Show enrollment QR and key")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Use a recovery code instead" }));
    expect(screen.getByRole("heading", { name: "Use a recovery code" })).toBeVisible();
    fireEvent.change(screen.getByLabelText("Recovery code"), { target: { value: "one-time-recovery" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    await waitFor(() => expect(complete).toHaveBeenCalledTimes(1));
  });
});
