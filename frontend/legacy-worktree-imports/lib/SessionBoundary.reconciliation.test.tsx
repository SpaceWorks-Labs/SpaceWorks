// SKIPPED (not run, not type-checked): imported from a development worktree, kept for reference.
// Reason: Not in release 0.12.0: written for string session contexts ("member", "staff:<slug>"); release SessionContext is "person" | "platform".
// Excluded from vitest (vite.config.ts) and outside tsconfig "include"; rewrite against the release code before moving back under src/.
import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Link, MemoryRouter } from "react-router-dom";
import { SessionBoundary } from "./SessionBoundary";
import { queryClientForContext } from "./queryClient";
import { clearAccessToken, setAccessToken } from "./api";
import { channelKeys } from "../features/notifications/channelsApi";
import { contextForRoute, setRouteSessionContext } from "./api/sessionContext";

vi.mock("./tenant", () => ({ useTenant: () => ({ mode: "central", slug: "" }) }));
const token = (id: number) => `header.${btoa(JSON.stringify({ user_id: id }))}.signature`;
afterEach(() => {
  clearAccessToken("member"); clearAccessToken("staff:lab"); clearAccessToken("platform");
  setRouteSessionContext("member");
});

it("partitions canonical notification keys by account, context and tenant", () => {
  setRouteSessionContext("member"); setAccessToken(token(1), "member");
  const member = channelKeys.preferences(11);
  expect(channelKeys.preferences(12)).not.toEqual(member);
  setAccessToken(token(2), "member");
  expect(channelKeys.preferences(11)).not.toEqual(member);
  setRouteSessionContext("staff:lab"); setAccessToken(token(1), "staff:lab");
  expect(channelKeys.preferences(11)).not.toEqual(member);
});

it("clears private queries when leaving a context and when signing out", () => {
  const member = queryClientForContext("member");
  const staff = queryClientForContext("staff:lab");
  render(<MemoryRouter initialEntries={["/member"]}><SessionBoundary>
    <Link to="/m/lab/admin/channels">Open staff channels</Link>
  </SessionBoundary></MemoryRouter>);
  member.setQueryData(["private"], "member data");
  staff.setQueryData(["private"], "staff data");
  fireEvent.click(screen.getByRole("link", { name: "Open staff channels" }));
  expect(member.getQueryData(["private"])).toBeUndefined();
  expect(staff.getQueryData(["private"])).toBe("staff data");
  clearAccessToken("staff:lab");
  expect(staff.getQueryData(["private"])).toBeUndefined();
});

it("keeps member restoration outside staff/platform namespaces", () => {
  expect(contextForRoute("/account/restore", "?context=platform")).toBe("member");
  expect(contextForRoute("/member/account", "?context=staff:lab")).toBe("member");
  expect(contextForRoute("/m/lab/admin/channels")).toBe("staff:lab");
  expect(contextForRoute("/admin/platform", "?context=platform")).toBe("platform");
});
