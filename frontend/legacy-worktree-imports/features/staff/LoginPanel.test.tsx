// SKIPPED (not run, not type-checked): imported from a development worktree, kept for reference.
// Reason: Not in release 0.12.0: LoginPanel is not in release 0.12.0 (staff sign-in was rebuilt; see useConsoleSession).
// Excluded from vitest (vite.config.ts) and outside tsconfig "include"; rewrite against the release code before moving back under src/.
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { LoginPanel } from "./LoginPanel";

describe("console password recovery links", () => {
  it.each([
    [false, "/m/alpha/admin/reset-password?step=request"],
    [false, "/admin/reset-password?step=request"],
    [true, "/admin/reset-password?context=platform&step=request"],
  ] as const)("links the sign-in panel to %s %s", (platform, recoveryHref) => {
    render(<MemoryRouter><LoginPanel guestOnly={false} isPending={false} platform={platform}
      recoveryHref={recoveryHref} onSubmit={vi.fn()} /></MemoryRouter>);
    expect(screen.getByRole("link", { name: "Forgot password?" })).toHaveAttribute("href", recoveryHref);
    expect(screen.queryByRole("button", { name: /Google|magic link|OTP/i })).not.toBeInTheDocument();
  });
});
