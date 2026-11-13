import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MfaEnrollmentScreen } from "../../staff/StaffGateScreens";
import { EnrolPasskeyInPlace } from "./EnrolPasskeyInPlace";
import { registerPasskey } from "./passkeyApi";
import { passkeysSupported } from "./webauthn";

const { setAccessToken } = vi.hoisted(() => ({ setAccessToken: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual("../../../lib/api"), setAccessToken }));
vi.mock("./passkeyApi", () => ({ registerPasskey: vi.fn() }));
vi.mock("./webauthn", async () => ({ ...await vi.importActual("./webauthn"), passkeysSupported: vi.fn() }));

const registered = (codes: string[] | null) => ({ passkey: { id: 1 }, recovery_codes: codes, access: "fresh", surface: "member", user: {} });

function show(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
  return invalidate;
}

beforeEach(() => { vi.resetAllMocks(); vi.mocked(passkeysSupported).mockReturnValue(true); });

describe("In-place passkey enrolment (S-D follow-up)", () => {
  it("adds a passkey, keeps the fresh session and refreshes the gate at once without new codes", async () => {
    vi.mocked(registerPasskey).mockResolvedValue(registered(null) as never);
    const invalidate = show(<EnrolPasskeyInPlace />);
    fireEvent.click(screen.getByRole("button", { name: "Add a passkey now" }));
    await waitFor(() => expect(setAccessToken).toHaveBeenCalledWith("fresh"));
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["staff", "me"] }));
  });

  it("shows first recovery codes and refreshes only after they are saved", async () => {
    vi.mocked(registerPasskey).mockResolvedValue(registered(["aaaa-bbbb", "cccc-dddd"]) as never);
    const invalidate = show(<EnrolPasskeyInPlace />);
    fireEvent.click(screen.getByRole("button", { name: "Add a passkey now" }));
    expect(await screen.findByText("aaaa-bbbb")).toBeVisible();
    expect(invalidate).not.toHaveBeenCalledWith({ queryKey: ["staff", "me"] });
    fireEvent.click(screen.getByRole("button", { name: "I've saved my codes" }));
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["staff", "me"] }));
  });

  it("explains a refusal such as passkeys being turned off for the person", async () => {
    vi.mocked(registerPasskey).mockRejectedValue(new Error("Passkeys are turned off for this account."));
    show(<EnrolPasskeyInPlace />);
    fireEvent.click(screen.getByRole("button", { name: "Add a passkey now" }));
    expect(await screen.findByText(/Passkeys are turned off|Couldn't add a passkey/)).toBeVisible();
  });

  it("sits on the mid-session enrolment screen beside the authenticator route", () => {
    show(<MfaEnrollmentScreen memberHref="/member" onSignOut={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Add a passkey now" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Set up two-step sign-in" })).toBeVisible();
  });
});
