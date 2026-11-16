import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MemberAuthPanel } from "./MemberAuthPanel";

const { publicV1Request } = vi.hoisted(() => ({ publicV1Request: vi.fn() }));
vi.mock("../../lib/api", () => ({ publicV1Request, staffRequest: vi.fn(), setAccessToken: vi.fn(), API_V1_URL: "/api/v1" }));
vi.mock("../auth/SocialSignInButtons", () => ({ SocialSignInButtons: () => null }));
vi.mock("../auth/passkeys/webauthn", async original => ({
  ...await original<typeof import("../auth/passkeys/webauthn")>(),
  passkeysSupported: () => false, passkeyAutofillSupported: () => Promise.resolve(false),
}));

function signIn() {
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "member@example.test" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "hunter22" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

beforeEach(() => {
  publicV1Request.mockReset();
  publicV1Request.mockImplementation((path: string) => Promise.resolve(path === "/config" ? {} : { access: "token", user: {} }));
});

describe("MemberAuthPanel after a correct sign-in", () => {
  it("shows a signing-in step, not the form again, while the host loads who signed in", async () => {
    render(<MemberAuthPanel onAuthenticated={() => new Promise<void>(() => undefined)} />);
    signIn();
    expect(await screen.findByRole("heading", { name: "Signing you in" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Email")).not.toBeInTheDocument();
  });

  it("returns to the form with the reason when the host cannot finish", async () => {
    render(<MemberAuthPanel onAuthenticated={() => Promise.reject(new Error("The server is unreachable."))} />);
    signIn();
    expect(await screen.findByText("The server is unreachable.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Email")).toBeInTheDocument());
  });
});
