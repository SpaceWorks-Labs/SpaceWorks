import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { requestReauthentication } from "../../lib/api/reauthentication";
import { apiError } from "../../lib/api/errors";
import { ReauthenticationDialog } from "./ReauthenticationDialog";
import { reauthenticationStatus } from "./reauthenticationApi";
import { reauthenticateWithPasskey } from "./passkeys/passkeyApi";
import { PasskeyCancelled } from "./passkeys/webauthn";

vi.mock("./reauthenticationApi", async original => ({
  ...await original<typeof import("./reauthenticationApi")>(),
  reauthenticationStatus: vi.fn(), verifyIdentity: vi.fn(), requestEnrollmentEmail: vi.fn(),
}));
vi.mock("./passkeys/passkeyApi", () => ({ reauthenticateWithPasskey: vi.fn() }));
const support = vi.hoisted(() => ({ passkeys: true }));
vi.mock("./passkeys/webauthn", async original => ({
  ...await original<typeof import("./passkeys/webauthn")>(), passkeysSupported: () => support.passkeys,
}));

const status = vi.mocked(reauthenticationStatus);
const passkey = vi.mocked(reauthenticateWithPasskey);
const STATUS = { verified: false, password_available: true, mfa_enabled: true, providers: [], passkey_available: true };

async function open() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <ReauthenticationDialog />
  </QueryClientProvider>);
  let verified: Promise<boolean> = Promise.resolve(false);
  act(() => { verified = requestReauthentication(); });
  await screen.findByRole("dialog");
  return () => verified;
}

beforeEach(() => { status.mockReset(); passkey.mockReset(); support.passkeys = true; });

describe("ReauthenticationDialog passkey option", () => {
  it("offers a passkey beside the password and authenticator", async () => {
    status.mockResolvedValue(STATUS as never);
    passkey.mockResolvedValue({ verified: true } as never);
    const verified = await open();
    expect(await screen.findByRole("button", { name: "Use a passkey" })).toBeInTheDocument();
    expect(screen.getByLabelText("Current password")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Use a passkey" }));
    await waitFor(() => expect(passkey).toHaveBeenCalled());
    await expect(verified()).resolves.toBe(true);
  });

  it("shows a passkey-only account just the passkey", async () => {
    status.mockResolvedValue({ ...STATUS, password_available: false, mfa_enabled: false } as never);
    await open();
    expect(await screen.findByRole("button", { name: "Use a passkey" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Current password")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Email a confirmation link/ })).not.toBeInTheDocument();
  });

  it("hides the passkey where the browser cannot run it", async () => {
    support.passkeys = false;
    status.mockResolvedValue(STATUS as never);
    await open();
    expect(await screen.findByLabelText("Current password")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Use a passkey" })).not.toBeInTheDocument();
  });

  it("stays quiet on a closed sheet and uses plain copy for a refusal", async () => {
    status.mockResolvedValue(STATUS as never);
    passkey.mockRejectedValueOnce(new PasskeyCancelled()).mockRejectedValueOnce(apiError(400, { detail: "raw", code: "passkey_failed" }));
    await open();
    fireEvent.click(await screen.findByRole("button", { name: "Use a passkey" }));
    await waitFor(() => expect(passkey).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByRole("button", { name: "Use a passkey" })).toBeEnabled());
    expect(screen.queryByText(/didn't work/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Use a passkey" }));
    expect(await screen.findByText(/That passkey didn't work here/)).toBeInTheDocument();
  });
});
