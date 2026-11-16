import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PlatformSocialAuthPanel } from "./PlatformSocialAuthPanel";

const { query, staffRequest } = vi.hoisted(() => ({
  query: vi.fn(),
  staffRequest: vi.fn(),
}));

vi.mock("../../lib/api", () => ({ staffRequest }));
vi.mock("./StaffPanels", async () => {
  const actual = await vi.importActual<typeof import("./StaffPanels")>("./StaffPanels");
  return { ...actual, useStaffGet: query };
});

describe("PlatformSocialAuthPanel", () => {
  beforeEach(() => {
    query.mockReset();
    staffRequest.mockReset();
    query.mockReturnValue({
      data: {
        google_enabled: true,
        apple_enabled: true,
        github_enabled: false,
        github_client_id: "",
        github_client_secret_set: false,
        google_web_client_id: "google-web",
        google_ios_client_id: "google-ios",
        google_android_client_id: "google-android",
        apple_service_id: "org.spaceworks.web",
        apple_native_app_ids: ["org.spaceworks.app"],
        apple_team_id: "TEAMID",
        apple_key_id: "KEYID",
        apple_private_key_set: true,
      },
      isLoading: false,
      error: null,
    });
  });

  it("never renders a stored Apple key and omits a blank replacement", async () => {
    staffRequest.mockResolvedValue({});
    render(
      <QueryClientProvider client={new QueryClient()}>
        <PlatformSocialAuthPanel />
      </QueryClientProvider>,
    );

    const keyInput = screen.getByPlaceholderText(/private key set/i);
    expect(keyInput).toHaveValue("");
    fireEvent.change(screen.getByRole("textbox", { name: "Web client ID" }), { target: { value: "google-web-updated" } });
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(staffRequest).toHaveBeenCalledTimes(1));
    const body = JSON.parse(staffRequest.mock.calls[0][1]?.body as string);
    expect(body.apple_private_key).toBeUndefined();
    expect(body.apple_native_app_ids).toEqual(["org.spaceworks.app"]);
  });

  it("sends a newly entered Apple key only as a write value", async () => {
    staffRequest.mockResolvedValue({});
    render(
      <QueryClientProvider client={new QueryClient()}>
        <PlatformSocialAuthPanel />
      </QueryClientProvider>,
    );

    fireEvent.change(screen.getByPlaceholderText(/private key set/i), {
      target: { value: "-----BEGIN PRIVATE KEY-----\nsecret" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(staffRequest).toHaveBeenCalledTimes(1));
    const body = JSON.parse(staffRequest.mock.calls[0][1]?.body as string);
    expect(body.apple_private_key).toContain("BEGIN PRIVATE KEY");
  });
});

describe("PlatformSocialAuthPanel provider switches", () => {
  const settings = {
    google_enabled: true, apple_enabled: true, github_enabled: true,
    google_web_client_id: "google-client", google_ios_client_id: "", google_android_client_id: "",
    apple_service_id: "apple-client", apple_native_app_ids: [], apple_team_id: "", apple_key_id: "",
    apple_private_key_set: false, github_client_id: "github-client", github_client_secret_set: true,
  };
  const mount = (data: typeof settings) => {
    query.mockReset();
    staffRequest.mockReset();
    query.mockReturnValue({ data, isLoading: false, error: null });
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: {
      queries: { retry: false }, mutations: { retry: false },
    } })}><PlatformSocialAuthPanel /></QueryClientProvider>);
  };

  it("shows only the providers chosen at install and saves only their credentials", async () => {
    mount({ ...settings, google_enabled: false, apple_enabled: false });
    staffRequest.mockResolvedValue({});
    expect(await screen.findByRole("textbox", { name: "GitHub client ID" })).toBeVisible();
    expect(screen.queryByText("Google OAuth clients")).not.toBeInTheDocument();
    expect(screen.queryByText("Apple Sign in")).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "GitHub client ID" }), { target: { value: "new-client" } });
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/platform/social-auth-settings", {
      method: "PATCH", body: JSON.stringify({ github_client_id: "new-client", clear_github_client_secret: false }),
    }));
  });

  it("shows all three configured provider forms when all were enabled", async () => {
    mount(settings);
    expect(await screen.findByRole("textbox", { name: "Web client ID" })).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Web Service ID" })).toBeVisible();
    expect(screen.getByRole("textbox", { name: "GitHub client ID" })).toBeVisible();
  });
});
