import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SocialSignInButtons } from "./SocialSignInButtons";

const { beginGithubBrowser, beginOidcBrowser, completeOidcBrowserCallback, mountGoogleButton, publicV1Request } = vi.hoisted(() => ({
  beginGithubBrowser: vi.fn(),
  beginOidcBrowser: vi.fn(),
  completeOidcBrowserCallback: vi.fn(),
  mountGoogleButton: vi.fn(),
  publicV1Request: vi.fn(),
}));

vi.mock("../../lib/api", () => ({ publicV1Request }));
vi.mock("./socialSdk", async () => {
  const actual = await vi.importActual<typeof import("./socialSdk")>("./socialSdk");
  return { ...actual, beginGithubBrowser, beginOidcBrowser, completeOidcBrowserCallback, mountGoogleButton };
});

describe("SocialSignInButtons", () => {
  beforeEach(() => {
    mountGoogleButton.mockReset();
    beginGithubBrowser.mockReset();
    beginOidcBrowser.mockReset();
    completeOidcBrowserCallback.mockReset();
    completeOidcBrowserCallback.mockResolvedValue(null);
    publicV1Request.mockReset();
  });

  it("starts GitHub on the member surface", async () => {
    publicV1Request.mockResolvedValue({ social_auth: { github: true } });
    beginGithubBrowser.mockResolvedValue(undefined);
    render(<SocialSignInButtons surface="member" onSuccess={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Continue with GitHub" }));
    await waitFor(() => expect(beginGithubBrowser).toHaveBeenCalledOnce());
  });

  it.each(["staff", "member"] as const)("hides GitHub for %s with member accounts disabled", async (surface) => {
    publicV1Request.mockResolvedValue({ social_auth: { github: true }, member_accounts: { enabled: false } });
    render(<SocialSignInButtons surface={surface} onSuccess={vi.fn()} />);
    await waitFor(() => expect(publicV1Request).toHaveBeenCalledWith("/config"));
    expect(screen.queryByRole("button", { name: "Continue with GitHub" })).not.toBeInTheDocument();
  });

  it("never shows GitHub on the staff surface even with member accounts enabled", async () => {
    publicV1Request.mockResolvedValue({ social_auth: { github: true } });
    render(<SocialSignInButtons surface="staff" onSuccess={vi.fn()} />);
    await waitFor(() => expect(publicV1Request).toHaveBeenCalledWith("/config"));
    expect(screen.queryByRole("button", { name: "Continue with GitHub" })).not.toBeInTheDocument();
  });

  it("stays absent when the public config omits social auth", async () => {
    publicV1Request.mockResolvedValue({ email_enabled: false });
    const { container } = render(
      <SocialSignInButtons surface="member" onSuccess={vi.fn()} />,
    );

    await waitFor(() => expect(publicV1Request).toHaveBeenCalledWith("/config"));
    expect(container).toBeEmptyDOMElement();
    expect(mountGoogleButton).not.toHaveBeenCalled();
  });

  it("mounts Google only with the frontend-safe configured client ID", async () => {
    publicV1Request.mockResolvedValue({
      social_auth: {
        google: { enabled: true, web_client_id: "google-web-client" },
      },
    });
    mountGoogleButton.mockResolvedValue(undefined);

    render(<SocialSignInButtons surface="staff" onSuccess={vi.fn()} />);

    expect(await screen.findByLabelText("Social sign in")).toBeInTheDocument();
    await waitFor(() =>
      expect(mountGoogleButton).toHaveBeenCalledWith(
        expect.any(HTMLElement),
        "google-web-client",
        "staff",
        expect.any(Function),
        expect.any(Function),
      ),
    );
  });

  it("drops the member surface when the deployment runs no member accounts", async () => {
    // The staff login screen reads the same endpoint and keeps its providers: staff
    // sign-in is core RBAC and is never gated. Only the member surface 404s behind it.
    publicV1Request.mockResolvedValue({
      social_auth: { google: { enabled: true, web_client_id: "google-web-client" } },
      member_accounts: { enabled: false },
    });
    mountGoogleButton.mockResolvedValue(undefined);

    const { container } = render(
      <SocialSignInButtons surface="member" onSuccess={vi.fn()} />,
    );

    await waitFor(() => expect(publicV1Request).toHaveBeenCalledWith("/config"));
    expect(container).toBeEmptyDOMElement();
    expect(mountGoogleButton).not.toHaveBeenCalled();

    render(<SocialSignInButtons surface="staff" onSuccess={vi.fn()} />);
    expect(await screen.findByLabelText("Social sign in")).toBeInTheDocument();
  });

  it("keeps only configured institution OIDC on an accounts-off member surface", async () => {
    publicV1Request.mockResolvedValue({
      social_auth: {
        google: { enabled: true, web_client_id: "google-web-client" },
        "oidc:campus": {
          enabled: true,
          display_name: "Campus SSO",
          client_id: "campus-client",
          issuer: "https://idp.example.test",
        },
      },
      member_accounts: { enabled: false },
    });
    beginOidcBrowser.mockResolvedValue(undefined);

    render(
      <SocialSignInButtons
        surface="member"
        email="member@example.test"
        makerspaceSlug="main-space"
        onSuccess={vi.fn()}
      />,
    );

    const button = await screen.findByRole("button", { name: "Continue with Campus SSO" });
    expect(mountGoogleButton).not.toHaveBeenCalled();
    fireEvent.click(button);
    await waitFor(() =>
      expect(beginOidcBrowser).toHaveBeenCalledWith(
        "campus",
        "member@example.test",
        "main-space",
        "member",
      ),
    );
  });

  it("offers OIDC staff sign-in and completes its browser callback", async () => {
    const result = { access: "staff-access", user: {}, outcome: "existing" };
    const success = vi.fn();
    publicV1Request.mockResolvedValue({ social_auth: {
      "oidc:campus": { enabled: true, display_name: "Campus SSO", client_id: "campus", issuer: "https://idp.example" },
    } });
    completeOidcBrowserCallback.mockResolvedValue(result);
    render(<QueryClientProvider client={new QueryClient()}><SocialSignInButtons surface="staff" onSuccess={success} /></QueryClientProvider>);
    await waitFor(() => expect(success).toHaveBeenCalledWith(result));
    fireEvent.click(await screen.findByRole("button", { name: "Continue with Campus SSO" }));
    await waitFor(() => expect(beginOidcBrowser).toHaveBeenCalledWith("campus", "", "", "staff"));
  });

  it("requires MFA returned by the staff OIDC callback before reporting success", async () => {
    publicV1Request.mockResolvedValue({ social_auth: {} });
    const success = vi.fn();
    completeOidcBrowserCallback.mockResolvedValue({ mfa_required: true, enrollment_required: false, challenge: "staff-proof", expires_in: 300 });
    render(<QueryClientProvider client={new QueryClient()}><SocialSignInButtons surface="staff" onSuccess={success} /></QueryClientProvider>);
    expect(await screen.findByRole("button", { name: /verify/i })).toBeInTheDocument();
    expect(success).not.toHaveBeenCalled();
  });

  it("hands MFA to the owning auth screen so it can show one layout", async () => {
    const onMfaChallenge = vi.fn();
    publicV1Request.mockResolvedValue({ social_auth: { google: { enabled: true, web_client_id: "google-client" } } });
    mountGoogleButton.mockResolvedValue(undefined);
    render(<SocialSignInButtons surface="staff" onSuccess={vi.fn()} onMfaChallenge={onMfaChallenge} />);
    await waitFor(() => expect(mountGoogleButton).toHaveBeenCalled());
    const challenge = { mfa_required: true, enrollment_required: false, challenge: "proof", expires_in: 300 };
    mountGoogleButton.mock.calls[0][3](challenge);
    expect(onMfaChallenge).toHaveBeenCalledWith(challenge);
    expect(screen.queryByRole("heading")).toBeNull();
  });
});
