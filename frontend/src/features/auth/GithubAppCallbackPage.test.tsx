import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/axe";
import { analyticsExcludedScreens } from "../../lib/analyticsRoutes0120";
import { safePage } from "../../lib/telemetry/policy";
import { replayRoute } from "../../lib/telemetry/replayRoutes";
import { analyticsTemplate, isBearerUrl } from "../../lib/webAnalytics";
import { GITHUB_APP_CALLBACK_PATH, GithubAppCallbackPage } from "./GithubAppCallbackPage";

const CODE = "one-time-github-code";
const LINK = `${GITHUB_APP_CALLBACK_PATH}?code=${CODE}&state=device-state`;
const fetchMock = vi.fn();

function show(open?: (href: string) => void) {
  return render(<MemoryRouter><GithubAppCallbackPage open={open} /></MemoryRouter>);
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  window.history.replaceState(null, "", LINK);
});
afterEach(() => {
  vi.unstubAllGlobals();
  document.head.querySelectorAll('meta[name="referrer"]').forEach(meta => meta.remove());
});

describe("GitHub app-link fallback page (decision 361)", () => {
  it("asks to open the app, never shows or sends the code, and scrubs the address bar", async () => {
    const { container } = show();
    expect(screen.getByRole("heading", { level: 1, name: "Open in the Space Works app" })).toBeVisible();
    expect(container.textContent).not.toContain(CODE);
    expect(container.innerHTML).not.toContain(CODE);
    expect(window.location.pathname).toBe(GITHUB_APP_CALLBACK_PATH);
    expect(window.location.search).toBe("");
    expect(document.head.querySelector('meta[name="referrer"]')).toHaveAttribute("content", "no-referrer");
    await new Promise(resolve => setTimeout(resolve, 20));
    expect(fetchMock).not.toHaveBeenCalled();
    await expectNoA11yViolations(container);
  });

  it("re-opens the very same link so the system can hand it to the app", () => {
    const open = vi.fn();
    show(open);
    expect(window.location.search).toBe("");  // scrubbed, but the link survives in memory
    fireEvent.click(screen.getByRole("button", { name: "Open the app" }));
    expect(open).toHaveBeenCalledWith(new URL(LINK, window.location.origin).href);
  });

  it("offers web sign-in and disables the retry once the link carries no code", () => {
    window.history.replaceState(null, "", GITHUB_APP_CALLBACK_PATH);
    show();
    expect(screen.getByRole("button", { name: "Open the app" })).toBeDisabled();
    expect(screen.getByRole("link", { name: "Sign in on the website" })).toHaveAttribute("href", "/member");
  });

  it("is never counted by analytics nor replayed", () => {
    expect(analyticsExcludedScreens).toContain(GITHUB_APP_CALLBACK_PATH);
    for (const path of [GITHUB_APP_CALLBACK_PATH, LINK]) {
      const url = new URL(path, window.location.origin);
      expect(isBearerUrl(url)).toBe(true);
      expect(analyticsTemplate(url)).toBeNull();
      expect(safePage(url)).toBeNull();
    }
    expect(replayRoute("posthog", GITHUB_APP_CALLBACK_PATH)).toBe(false);
    expect(replayRoute("clarity", GITHUB_APP_CALLBACK_PATH)).toBe(false);
  });
});
