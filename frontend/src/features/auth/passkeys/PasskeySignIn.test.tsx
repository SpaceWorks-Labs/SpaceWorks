import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiError } from "../../../lib/api/errors";
import { finishPasskeySignIn, passkeySignInOptions } from "./passkeyApi";
import { PasskeySignInButton } from "./PasskeySignInButton";
import { usePasskeySignIn } from "./usePasskeySignIn";
import { PasskeyCancelled, passkeyAutofillSupported, passkeysSupported } from "./webauthn";

vi.mock("./passkeyApi", () => ({ passkeySignInOptions: vi.fn(), finishPasskeySignIn: vi.fn() }));
vi.mock("./webauthn", async original => ({
  ...await original<typeof import("./webauthn")>(),
  passkeysSupported: vi.fn(), passkeyAutofillSupported: vi.fn(),
}));
vi.mock("@simplewebauthn/browser", async original => ({
  ...await original<typeof import("@simplewebauthn/browser")>(),
  WebAuthnAbortService: { cancelCeremony: vi.fn() },
}));

const options = vi.mocked(passkeySignInOptions);
const finish = vi.mocked(finishPasskeySignIn);
const supported = vi.mocked(passkeysSupported);
const autofill = vi.mocked(passkeyAutofillSupported);
const ceremony = { ceremony: "c-1", options: { challenge: "x" } } as never;

function Harness({ enabled = true, onSignedIn = vi.fn() }: { enabled?: boolean; onSignedIn?: (value: unknown) => void }) {
  const passkey = usePasskeySignIn({ enabled, onSignedIn });
  return <div>
    <input aria-label="Email" autoComplete={passkey.autofill ? "username webauthn" : "email"} />
    {passkey.supported ? <PasskeySignInButton pending={passkey.pending} error={passkey.error} onClick={passkey.signIn} /> : <p>No passkey control</p>}
  </div>;
}

beforeEach(() => {
  [options, finish, supported, autofill].forEach(mock => mock.mockReset());
  supported.mockReturnValue(true);
  autofill.mockResolvedValue(false);
});

describe("passkey sign-in", () => {
  it("shows no control when the browser has no WebAuthn", () => {
    supported.mockReturnValue(false);
    render(<Harness />);
    expect(screen.getByText("No passkey control")).toBeInTheDocument();
    expect(autofill).not.toHaveBeenCalled();
  });

  it("shows no control when the config turns passkeys off", () => {
    render(<Harness enabled={false} />);
    expect(screen.getByText("No passkey control")).toBeInTheDocument();
  });

  it("offers passkeys in autofill when conditional UI is supported, without opening a prompt", async () => {
    autofill.mockResolvedValue(true);
    options.mockResolvedValue(ceremony);
    finish.mockReturnValue(new Promise(() => undefined));
    render(<Harness />);
    await waitFor(() => expect(screen.getByLabelText("Email")).toHaveAttribute("autocomplete", "username webauthn"));
    await waitFor(() => expect(finish).toHaveBeenCalledWith(ceremony, true));
  });

  it("keeps the plain email field when conditional UI is missing", async () => {
    render(<Harness />);
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByLabelText("Email")).toHaveAttribute("autocomplete", "email");
    expect(options).not.toHaveBeenCalled();
  });

  it("signs in from the button", async () => {
    const onSignedIn = vi.fn();
    options.mockResolvedValue(ceremony);
    finish.mockResolvedValue({ access: "token" } as never);
    render(<Harness onSignedIn={onSignedIn} />);
    fireEvent.click(screen.getByRole("button", { name: "Sign in with a passkey" }));
    await waitFor(() => expect(onSignedIn).toHaveBeenCalledWith({ access: "token" }));
    expect(finish).toHaveBeenCalledWith(ceremony, false);
  });

  it("stays quiet when the person closes the sheet, and uses plain copy for a failure", async () => {
    options.mockResolvedValue(ceremony);
    finish.mockRejectedValueOnce(new PasskeyCancelled());
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Sign in with a passkey" }));
    await waitFor(() => expect(finish).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByRole("button", { name: "Sign in with a passkey" })).toBeEnabled());
    expect(screen.getByRole("alert")).toBeEmptyDOMElement();
    finish.mockRejectedValueOnce(apiError(400, { detail: "raw", code: "passkey_failed" }));
    fireEvent.click(screen.getByRole("button", { name: "Sign in with a passkey" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("That passkey didn't work here."));
  });
});
