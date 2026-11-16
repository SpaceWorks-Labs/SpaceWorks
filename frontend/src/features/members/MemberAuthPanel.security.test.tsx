import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiError } from "../../lib/api/errors";
import { expectNoA11yViolations } from "../../test/axe";
import { MemberAuthPanel } from "./MemberAuthPanel";

const { publicV1Request, staffRequest } = vi.hoisted(() => ({ publicV1Request: vi.fn(), staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ publicV1Request, staffRequest, setAccessToken: vi.fn(), API_V1_URL: "/api/v1" }));
vi.mock("../auth/SocialSignInButtons", () => ({ SocialSignInButtons: () => null }));
const support = vi.hoisted(() => ({ passkeys: true }));
vi.mock("../auth/passkeys/webauthn", async original => ({
  ...await original<typeof import("../auth/passkeys/webauthn")>(),
  passkeysSupported: () => support.passkeys, passkeyAutofillSupported: () => Promise.resolve(false),
}));
const turnstile = vi.hoisted(() => ({ token: vi.fn<(token: string) => void>() }));
vi.mock("../../components/auth/TurnstileWidget", () => ({
  TurnstileWidget: ({ onToken }: { onToken: (token: string) => void }) => {
    turnstile.token.mockImplementation(onToken);
    return <div role="group" aria-label="Confirm you're a person" />;
  },
}));

function config(value: Record<string, unknown>) {
  publicV1Request.mockImplementation((path: string) => path === "/config" ? Promise.resolve(value) : Promise.reject(new Error("unexpected")));
}
function signIn() {
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "member@example.test" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "hunter22" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
}
const logins = () => publicV1Request.mock.calls.filter(([path]) => path === "/auth/login");

beforeEach(() => { publicV1Request.mockReset(); staffRequest.mockReset(); turnstile.token.mockReset(); support.passkeys = true; });

describe("MemberAuthPanel login security", () => {
  it("offers a passkey only when the config turns passkeys on", async () => {
    config({ passkeys_enabled: true });
    const { container } = render(<MemberAuthPanel onAuthenticated={vi.fn()} />);
    expect(await screen.findByRole("button", { name: "Sign in with a passkey" })).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("shows no passkey control without the config switch", async () => {
    config({});
    render(<MemberAuthPanel onAuthenticated={vi.fn()} />);
    await waitFor(() => expect(publicV1Request).toHaveBeenCalledWith("/config"));
    expect(screen.queryByRole("button", { name: "Sign in with a passkey" })).not.toBeInTheDocument();
  });

  it("sends only username and password, then resubmits with the Turnstile token after captcha_required", async () => {
    config({ turnstile_site_key: "site-key" });
    render(<MemberAuthPanel onAuthenticated={vi.fn()} />);
    await waitFor(() => expect(publicV1Request).toHaveBeenCalledWith("/config"));
    publicV1Request.mockImplementation((path: string) => path === "/auth/login"
      ? Promise.reject(apiError(400, { code: "captcha_required", turnstile_site_key: "site-key", turnstile_action: "login" }))
      : Promise.resolve({ turnstile_site_key: "site-key" }));
    signIn();
    expect(await screen.findByRole("group", { name: "Confirm you're a person" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(JSON.parse(logins()[0][1].body)).toEqual({ username: "member@example.test", password: "hunter22" });
    expect(logins()[0][1].headers).toEqual({});
    turnstile.token("turnstile-token");
    await waitFor(() => expect(logins()).toHaveLength(2));
    expect(logins()[1][1].headers).toEqual({ "X-Turnstile-Token": "turnstile-token" });
  });

  it("shows the IP block in plain words with the wait", async () => {
    config({});
    render(<MemberAuthPanel onAuthenticated={vi.fn()} />);
    await waitFor(() => expect(publicV1Request).toHaveBeenCalledWith("/config"));
    publicV1Request.mockImplementation((path: string) => path === "/auth/login"
      ? Promise.reject(apiError(429, { code: "ip_blocked", detail: "raw" }, new Headers({ "Retry-After": "600" })))
      : Promise.resolve({}));
    signIn();
    expect(await screen.findByRole("alert")).toHaveTextContent("Too many failed sign-ins from your network. Try again in about 10 minutes.");
  });

  it("links a breached password back to the password field", async () => {
    config({});
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemberAuthPanel onAuthenticated={vi.fn()} /></QueryClientProvider>);
    await waitFor(() => expect(publicV1Request).toHaveBeenCalledWith("/config"));
    publicV1Request.mockImplementation((path: string) => path === "/auth/member-sign-up"
      ? Promise.reject(apiError(400, { code: "password_breached", detail: "raw" }))
      : Promise.resolve(path.startsWith("/handles/check") ? (path.includes("handle=") ? { available: true, reason: "", suggestion: null } : { available: null, reason: "", suggestion: "ada" }) : {}));
    fireEvent.click(screen.getByRole("radio", { name: "Create account" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Ada" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ada@example.test" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password1" } });
    await waitFor(() => expect(screen.getByRole("button", { name: "Create account" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/known data breach/);
    expect(alert.textContent?.toLowerCase()).not.toContain("hack");
    fireEvent.click(screen.getByRole("link", { name: "Choose another password" }));
    expect(screen.getByLabelText("Password")).toHaveFocus();
  });
});
