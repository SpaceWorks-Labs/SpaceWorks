import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it } from "vitest";

import { contextForRoute, setRouteSessionContext, type SessionContext } from "../../lib/api/sessionContext";
import { authHeaders, clearAccessToken, getAccessToken, setAccessToken } from "../../lib/api/client";
import { SessionBoundary } from "../../lib/SessionBoundary";
import { MfaEnrollmentScreen, MfaGraceBanner } from "./StaffGateScreens";

afterEach(() => { clearAccessToken("person"); clearAccessToken("platform"); setRouteSessionContext("person"); window.history.replaceState({}, "", "/"); });

function SelectedSession() {
  return <output aria-label="Selected bearer">{new Headers(authHeaders()).get("Authorization") ?? "none"}</output>;
}

it.each([
  ["person", "/m/lab/admin/events?view=calendar", "Set up two-step sign-in"],
  ["person", "/m/lab/admin/events?view=calendar", "Set it up now →"],
  ["platform", "/admin/platform-dashboard?context=platform", "Set up two-step sign-in"],
  ["platform", "/admin/platform-dashboard?context=platform", "Set it up now →"],
] as const)("clicking %s %s via %s keeps its own identity", (context: SessionContext, path, name) => {
  window.history.replaceState({}, "", path);
  setRouteSessionContext(context);
  setAccessToken("token:person", "person"); setAccessToken("token:platform", "platform");
  render(<MemoryRouter initialEntries={[path]}><SessionBoundary><Routes>
    <Route path="/mfa" element={<SelectedSession />} />
    <Route path="*" element={<><MfaEnrollmentScreen memberHref="/m/lab/member" onSignOut={() => undefined} />
      <MfaGraceBanner endsAt="2026-11-09T00:00:00Z" /></>} />
  </Routes></SessionBoundary>
  </MemoryRouter>);
  const link = screen.getByRole("link", { name });
  const url = new URL(link.getAttribute("href")!, window.location.origin);
  expect(url.pathname).toBe("/mfa");
  expect(url.searchParams.get("return")).toBe(path);
  fireEvent.click(link);
  expect(screen.getByLabelText("Selected bearer")).toHaveTextContent(`Bearer token:${context}`);
  expect(contextForRoute(url.pathname, url.search)).toBe(context);
  expect(url.searchParams.get("context")).toBe(context === "platform" ? "platform" : null);
  expect(getAccessToken(context === "platform" ? "person" : "platform")).toBe(`token:${context === "platform" ? "person" : "platform"}`);
});
