import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiError } from "../../lib/api/errors";
import { expectNoA11yViolations } from "../../test/axe";
import { MfaFlow } from "./MfaFlow";
import { mfaRequest, resendLoginCode, type MfaChallenge } from "./mfaApi";
import { verifyPasskeyFactor } from "./passkeys/passkeyApi";
import { PasskeyCancelled } from "./passkeys/webauthn";

vi.mock("./mfaApi", () => ({ mfaRequest: vi.fn(), resendLoginCode: vi.fn() }));
vi.mock("./passkeys/passkeyApi", () => ({ verifyPasskeyFactor: vi.fn() }));
const support = vi.hoisted(() => ({ passkeys: true }));
vi.mock("./passkeys/webauthn", async original => ({
  ...await original<typeof import("./passkeys/webauthn")>(),
  passkeysSupported: () => support.passkeys,
}));

const request = vi.mocked(mfaRequest);
const resend = vi.mocked(resendLoginCode);
const passkey = vi.mocked(verifyPasskeyFactor);
const base: MfaChallenge = { mfa_required: true, enrollment_required: false, challenge: "challenge-token-0000000", expires_in: 300 };

function mount(challenge: Partial<MfaChallenge>) {
  const complete = vi.fn();
  const view = render(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
    <MfaFlow challenge={{ ...base, ...challenge }} onComplete={complete} onCancel={vi.fn()} />
  </QueryClientProvider>);
  return { complete, ...view };
}

beforeEach(() => { request.mockReset(); resend.mockReset(); passkey.mockReset(); support.passkeys = true; });

describe("MfaFlow factor picker", () => {
  it("starts on the first listed factor and offers the others as switches", async () => {
    const { container } = mount({ purpose: "login", factors: ["totp", "passkey", "recovery"] });
    expect(screen.getByRole("heading", { level: 1, name: "Enter your 6-digit code" })).toBeVisible();
    expect(screen.getByLabelText("Authenticator code")).toHaveAttribute("inputmode", "numeric");
    const others = screen.getByRole("group", { name: "Other ways to verify" });
    expect(others).toHaveTextContent("Use a passkey instead");
    expect(others).toHaveTextContent("Use a recovery code instead");
    expect(others).not.toHaveTextContent("Email me a code instead");
    await expectNoA11yViolations(container);
  });

  it("answers with the chosen factor", async () => {
    request.mockResolvedValue({ access: "a", surface: "member", user: {} });
    const { complete } = mount({ purpose: "login", factors: ["totp", "recovery"] });
    fireEvent.click(screen.getByRole("button", { name: "Use a recovery code instead" }));
    expect(screen.getByRole("heading", { level: 1, name: "Use a recovery code" })).toBeVisible();
    fireEvent.change(screen.getByLabelText("Recovery code"), { target: { value: "abcd-efgh" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    await waitFor(() => expect(complete).toHaveBeenCalled());
    expect(request).toHaveBeenCalledWith("/auth/mfa/verify", { challenge: base.challenge, code: "abcd-efgh", factor: "recovery" });
  });

  it("verifies a passkey through the browser and stays quiet when the sheet is closed", async () => {
    passkey.mockRejectedValueOnce(new PasskeyCancelled());
    const { complete } = mount({ purpose: "login", factors: ["passkey", "totp"] });
    expect(screen.getByRole("heading", { level: 1, name: "Use your passkey" })).toBeVisible();
    expect(screen.queryByLabelText(/code/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Use your passkey" }));
    await waitFor(() => expect(passkey).toHaveBeenCalledWith(base.challenge));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    passkey.mockResolvedValueOnce({ access: "a", surface: "member", user: {} });
    fireEvent.click(screen.getByRole("button", { name: "Use your passkey" }));
    await waitFor(() => expect(complete).toHaveBeenCalled());
  });

  it("drops the passkey where the browser cannot run it", () => {
    support.passkeys = false;
    mount({ purpose: "login", factors: ["passkey", "totp"] });
    expect(screen.getByRole("heading", { level: 1, name: "Enter your 6-digit code" })).toBeVisible();
    expect(screen.queryByText("Use a passkey instead")).not.toBeInTheDocument();
  });

  it("explains an unusual sign-in and shows the code error in plain words", async () => {
    request.mockRejectedValue(apiError(400, { detail: "That code is not right or has expired.", code: "login_code_invalid" }));
    const { container } = mount({ purpose: "risk", factors: ["email_code"] });
    expect(screen.getByRole("heading", { level: 1, name: "Check your email" })).toBeVisible();
    expect(screen.getByText(/We don't recognise this device or network/)).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Other ways to verify" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Emailed code"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That code didn't match or has expired.");
    expect(screen.getByRole("alert")).not.toHaveTextContent("login_code_invalid");
    expect(request).toHaveBeenCalledWith("/auth/mfa/verify", { challenge: base.challenge, code: "123456", factor: "email_code" });
    await expectNoA11yViolations(container);
  });

  it("counts resends down from the server and stops at none", async () => {
    resend.mockResolvedValueOnce({ sent: true, expires_in: 600, resends_left: 1 })
      .mockResolvedValueOnce({ sent: true, expires_in: 600, resends_left: 0 });
    mount({ purpose: "risk", factors: ["email_code"] });
    expect(screen.getByText("2 resends left.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Send a new code" }));
    expect(await screen.findByText("We sent a new code. 1 resend left.")).toBeInTheDocument();
    expect(resend).toHaveBeenCalledWith(base.challenge, {});
    fireEvent.click(screen.getByRole("button", { name: "Send a new code" }));
    expect(await screen.findByText("We sent a new code. That was the last resend.")).toBeInTheDocument();
    expect(screen.getByText("No resends left. Restart sign-in to get a new code.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send a new code" })).toBeDisabled();
  });

  it("keeps the pre-S-B wording for a challenge with no factors", () => {
    mount({});
    expect(screen.getByLabelText("Authenticator or recovery code")).toBeInTheDocument();
  });

  it("forced enrolment explains the staff rule and points to adding a passkey", () => {
    mount({ enrollment_required: true, purpose: "login", factors: [] });
    expect(screen.getByRole("heading", { level: 1, name: "Set up two-step sign-in" })).toBeVisible();
    expect(screen.getByText(/Staff need two-step sign-in before the staff console opens/)).toHaveTextContent(/add a passkey/);
    expect(screen.getByRole("button", { name: "Show enrollment QR and key" })).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Other ways to verify" })).not.toBeInTheDocument();
  });
});
