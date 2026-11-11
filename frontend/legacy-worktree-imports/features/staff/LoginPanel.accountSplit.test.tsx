// SKIPPED (not run, not type-checked): imported from a development worktree, kept for reference.
// Reason: Not in release 0.12.0: LoginPanel is not in release 0.12.0 (staff sign-in was rebuilt; see useConsoleSession).
// Excluded from vitest (vite.config.ts) and outside tsconfig "include"; rewrite against the release code before moving back under src/.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { LoginPanel } from "./LoginPanel";
import { ChangePasswordGate } from "./ChangePasswordGate";

it("offers only username-or-email and password for staff even if member methods are disabled", () => {
  const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
  const submit = vi.fn();
  render(<MemoryRouter><LoginPanel guestOnly={false} isPending={false} onSubmit={submit} /></MemoryRouter>);
  fireEvent.change(screen.getByLabelText("Username or email"), { target: { value: "staff@example.com" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "temporary" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(submit).toHaveBeenCalledWith({ username: "staff@example.com", password: "temporary" });
  expect(screen.queryByText(/Google|Apple|GitHub|phone|magic link/i)).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Forgot password?" })).toHaveAttribute("href", "/admin/reset-password?step=request");
  expect(fetcher).not.toHaveBeenCalled(); vi.unstubAllGlobals();
});

it("requires confirmation and finishes forced password change before opening the console", async () => {
  const changed = vi.fn();
  const fetcher = vi.fn(async () => new Response(JSON.stringify({ detail: "Password changed." }), { status: 200 }));
  vi.stubGlobal("fetch", fetcher);
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>
    <ChangePasswordGate username="staff.forge" onChanged={changed} onSignOut={() => {}} />
  </MemoryRouter></QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "temporary" } });
  fireEvent.change(screen.getByLabelText("New password"), { target: { value: "New-secret-012345" } });
  expect(screen.getByRole("button", { name: "Update password" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "New-secret-012345" } });
  fireEvent.click(screen.getByRole("button", { name: "Update password" }));
  await waitFor(() => expect(changed).toHaveBeenCalledOnce());
  expect(JSON.parse((fetcher.mock.calls[0] as unknown as [string, RequestInit])[1].body as string)).toEqual({ current_password: "temporary", new_password: "New-secret-012345" });
  vi.unstubAllGlobals();
});
