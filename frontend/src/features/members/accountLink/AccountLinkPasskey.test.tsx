import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { memberRequest, StructuredApiError } from "../../../lib/api";
import { getPasskeyAssertion, passkeysSupported, PasskeyCancelled } from "../../auth/passkeys/webauthn";
import { AccountLinkCard } from "./AccountLinkCard";

vi.mock("../../../lib/api", async () => ({ ...await vi.importActual("../../../lib/api"), memberRequest: vi.fn() }));
vi.mock("../../auth/passkeys/webauthn", async () => ({ ...await vi.importActual("../../auth/passkeys/webauthn"),
  getPasskeyAssertion: vi.fn(), passkeysSupported: vi.fn() }));

const base = "/auth/account-merge";
const intent = (state = "pending") => ({ intent_id: "i-1", method: "credentials", state, expires_at: "2026-11-03T12:00:00Z" });
const preview = { source: { id: 2, username: "old-staff", display_name: "Ada" },
  privilege_diff: { roles_gained: [], duplicate_staff_rows: [] }, grace_opens: false,
  moves: { repoint: { rows: 0 }, keep_on_shell: { rows: 0 }, unique_resolve: { rows: 0, kept_on_shell: 0 } },
  conflicts: [], preview_sha256: "abc", expires_at: "2026-11-03T12:00:00Z" };

function api(options: unknown = { ceremony: "c-1", options: { challenge: "x" } }) {
  vi.mocked(memberRequest).mockImplementation(async (path: string) => {
    const action = path.split("/").pop();
    if (action === "passkey-options") { if (options instanceof Error) throw options; return options; }
    return ({ start: intent(), prove: intent("proved"), preview } as Record<string, unknown>)[action ?? ""];
  });
}

async function toProve() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <MemoryRouter><AccountLinkCard /></MemoryRouter></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Link an account" }));
  fireEvent.change(await screen.findByRole("textbox", { name: "Username or email of the other account" }), { target: { value: "old-staff" } });
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
  return screen.findByLabelText("Password of the other account");
}

beforeEach(() => { vi.resetAllMocks(); vi.mocked(passkeysSupported).mockReturnValue(true); });

describe("Link an account with the other account's passkey (#65)", () => {
  it("checks the password, asks the device, then proves with the passkey instead of a code", async () => {
    api();
    vi.mocked(getPasskeyAssertion).mockResolvedValue({ id: "cred" } as never);
    const password = await toProve();
    const button = screen.getByRole("button", { name: "Use its passkey instead" });
    expect(button).toBeDisabled();
    fireEvent.change(password, { target: { value: "hunter22" } });
    fireEvent.click(button);
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith(`${base}/i-1/prove`, { method: "POST",
      body: JSON.stringify({ password: "hunter22", passkey: { ceremony: "c-1", credential: { id: "cred" } } }) }));
    expect(memberRequest).toHaveBeenCalledWith(`${base}/i-1/passkey-options`, { method: "POST", body: JSON.stringify({ password: "hunter22" }) });
    expect(getPasskeyAssertion).toHaveBeenCalledWith({ challenge: "x" });
    expect(await screen.findByRole("button", { name: "Continue to confirm" })).toBeVisible();
  });

  it("says nothing when the person closes the device sheet, and explains a missing passkey", async () => {
    api();
    vi.mocked(getPasskeyAssertion).mockRejectedValue(new PasskeyCancelled());
    fireEvent.change(await toProve(), { target: { value: "hunter22" } });
    fireEvent.click(screen.getByRole("button", { name: "Use its passkey instead" }));
    await waitFor(() => expect(getPasskeyAssertion).toHaveBeenCalled());
    expect(screen.queryByRole("alert")).toBeNull();
    api(new StructuredApiError(400, { code: "factor_enrolment_required" }));
    fireEvent.click(screen.getByRole("button", { name: "Use its passkey instead" }));
    expect(await screen.findByText(/Use the emailed codes instead/)).toBeVisible();
  });

  it("hides the passkey choice where the browser has no passkeys", async () => {
    vi.mocked(passkeysSupported).mockReturnValue(false);
    api();
    await toProve();
    expect(screen.queryByRole("button", { name: "Use its passkey instead" })).toBeNull();
  });
});
