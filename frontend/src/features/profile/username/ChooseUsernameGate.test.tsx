import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearAccessToken, logout, memberRequest, publicV1Request, setAccessToken } from "../../../lib/api";
import { ChooseUsernameGate } from "./ChooseUsernameGate";
import { clearUsernameReview, markUsernameReview, takeUsernameReview } from "./usernameApi";

vi.mock("../../../lib/api", async original => ({ ...(await original<typeof import("../../../lib/api")>()), memberRequest: vi.fn(), publicV1Request: vi.fn(), logout: vi.fn() }));

let me: Record<string, unknown> = {};
function show() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ChooseUsernameGate /><button>Page behind</button></QueryClientProvider>);
}
const claims = () => vi.mocked(memberRequest).mock.calls.filter(([path, options]) => path === "/member/profile/handle" && options?.method === "POST");

describe("ChooseUsernameGate (decision 308)", () => {
  beforeEach(() => {
    me = { handle_required: true, handle_suggestion: "ada.l", display_name: "Ada Lovelace", email: "ada@example.test" };
    vi.mocked(memberRequest).mockReset().mockImplementation(async (path: string) => {
      if (path === "/auth/me") return me;
      return { handle: "ada.l", claimed_at: "", changed_at: "" };
    });
    vi.mocked(publicV1Request).mockReset().mockResolvedValue({ available: true, reason: "", suggestion: null });
    vi.mocked(logout).mockReset().mockResolvedValue(undefined);
    setAccessToken("header.e30.sig", "person");
  });
  afterEach(() => clearAccessToken("person"));

  it("blocks with a pre-filled username that one tap accepts", async () => {
    show();
    const dialog = await screen.findByRole("dialog", { name: "Choose your username" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    await waitFor(() => expect(screen.getByLabelText("Username")).toHaveValue("ada.l"));
    const accept = await screen.findByRole("button", { name: "Use @ada.l" });
    await waitFor(() => expect(accept).toBeEnabled());
    fireEvent.click(accept);
    await waitFor(() => expect(claims()).toHaveLength(1));
    expect(JSON.parse(String(claims()[0][1]?.body))).toEqual({ handle: "ada.l" });
  });

  it("cannot be skipped: no close control and Escape leaves it open", async () => {
    show();
    const dialog = await screen.findByRole("dialog", { name: "Choose your username" });
    expect(screen.queryByRole("button", { name: /close|skip|later/i })).toBeNull();
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.getByRole("dialog", { name: "Choose your username" })).toBeVisible();
  });

  it("refuses a taken username", async () => {
    vi.mocked(publicV1Request).mockResolvedValue({ available: false, reason: "taken", suggestion: null });
    show();
    expect(await screen.findByText("That username is taken.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Use @ada.l" })).toBeDisabled();
  });

  it("still lets the person sign out", async () => {
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(logout).toHaveBeenCalledWith("person"));
  });

  it("stays out of the way when the account already has a username", async () => {
    me = { handle_required: false };
    show();
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/auth/me"));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("does nothing for a logged-out visitor", () => {
    clearAccessToken("person");
    show();
    expect(memberRequest).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("removes a cached blocking dialog when the account becomes restricted", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><ChooseUsernameGate /></QueryClientProvider>);
    expect(await screen.findByRole("dialog")).toBeVisible();
    const { StructuredApiError } = await import("../../../lib/api");
    vi.mocked(memberRequest).mockRejectedValue(new StructuredApiError(401, { code: "account_restricted" }));
    await client.invalidateQueries();
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});

describe("after a social sign-up", () => {
  beforeEach(() => {
    me = { handle: "ada.l", handle_required: false, display_name: "Ada Lovelace" };
    vi.mocked(memberRequest).mockReset().mockImplementation(async (path: string) => path === "/auth/me" ? me : { handle: "ada.l", claimed_at: "", changed_at: "" });
    vi.mocked(publicV1Request).mockReset().mockResolvedValue({ available: true, reason: "", suggestion: null });
    setAccessToken("header.e30.sig", "person");
    markUsernameReview();
  });
  afterEach(() => { clearAccessToken("person"); clearUsernameReview(); });

  it("shows 'Your username is X, change it?' once, and lets the person keep it", async () => {
    show();
    expect(await screen.findByRole("dialog", { name: "Your username is @ada.l" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Keep @ada.l" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(takeUsernameReview()).toBe(false);
  });

  it("lets the person change it through the normal handle claim", async () => {
    show();
    await screen.findByRole("dialog", { name: "Your username is @ada.l" });
    fireEvent.click(screen.getByRole("button", { name: "Change it" }));
    fireEvent.change(await screen.findByLabelText("Username"), { target: { value: "ada.lovelace" } });
    await screen.findByText("That username is free.");
    fireEvent.click(screen.getByRole("button", { name: "Use @ada.lovelace" }));
    await waitFor(() => expect(claims()).toHaveLength(1));
    expect(JSON.parse(String(claims()[0][1]?.body))).toEqual({ handle: "ada.lovelace" });
  });

  it("is not blocking: Escape dismisses it", async () => {
    show();
    fireEvent.keyDown(await screen.findByRole("dialog", { name: "Your username is @ada.l" }), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});
