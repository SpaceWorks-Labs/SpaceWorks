import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MemberAuthPanel } from "./MemberAuthPanel";

const { publicV1Request, staffRequest } = vi.hoisted(() => ({ publicV1Request: vi.fn(), staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ publicV1Request, staffRequest, setAccessToken: vi.fn(), API_V1_URL: "/api/v1" }));
vi.mock("../auth/SocialSignInButtons", () => ({ SocialSignInButtons: () => null }));

let taken: string[] = [];
function serve() {
  publicV1Request.mockImplementation(async (path: string) => {
    if (path === "/config") return { self_serve_accounts: true, password_login: true };
    if (path.startsWith("/handles/check")) {
      const handle = new URL(path, "http://x").searchParams.get("handle");
      if (!handle) return { available: null, reason: "", suggestion: "ada.l" };
      return taken.includes(handle) ? { handle, available: false, reason: "taken", suggestion: "ada.l" } : { handle, available: true, reason: "", suggestion: null };
    }
    return {};
  });
}
const signUpBody = () => {
  const call = publicV1Request.mock.calls.find(([path]) => path === "/auth/member-sign-up");
  return call ? JSON.parse(String(call[1].body)) : undefined;
};
async function openSignUp() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemberAuthPanel onAuthenticated={vi.fn()} /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("radio", { name: "Create account" }));
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Ada Lovelace" } });
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ada@example.test" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password1" } });
}

describe("sign-up username (decision 308)", () => {
  beforeEach(() => { publicV1Request.mockReset(); staffRequest.mockReset(); taken = []; serve(); });

  it("pre-fills a suggestion, checks it live and sends it with the sign-up", async () => {
    await openSignUp();
    const field = await screen.findByLabelText("Username");
    await waitFor(() => expect(field).toHaveValue("ada.l"));
    expect(await screen.findByText("That username is free.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(signUpBody()).toMatchObject({ handle: "ada.l", display_name: "Ada Lovelace", email: "ada@example.test" }));
  });

  it("blocks a taken username and says so", async () => {
    taken = ["ada"];
    await openSignUp();
    const field = await screen.findByLabelText("Username");
    await waitFor(() => expect(field).toHaveValue("ada.l"));
    fireEvent.change(field, { target: { value: "Ada" } });
    expect(await screen.findByText("That username is taken.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Create account" })).toBeDisabled();
  });

  it("rejects a username that breaks the grammar without asking the server", async () => {
    await openSignUp();
    const field = await screen.findByLabelText("Username");
    fireEvent.change(field, { target: { value: "-bad-" } });
    expect(await screen.findByText(/Use 3–30 lowercase letters/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Create account" })).toBeDisabled();
    expect(publicV1Request.mock.calls.some(([path]) => String(path).includes("handle=-bad-"))).toBe(false);
  });

  it("keeps what the person typed instead of overwriting it with the suggestion", async () => {
    await openSignUp();
    const field = await screen.findByLabelText("Username");
    fireEvent.change(field, { target: { value: "my.name" } });
    await waitFor(() => expect(screen.getByText("That username is free.")).toBeVisible());
    expect(field).toHaveValue("my.name");
  });

  it("does not ask for a username when signing in", async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemberAuthPanel onAuthenticated={vi.fn()} /></QueryClientProvider>);
    await screen.findByRole("radio", { name: "Create account" });
    expect(screen.queryByLabelText("Username")).toBeNull();
  });
});
