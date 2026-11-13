import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { ChannelPreferences } from "./ChannelPreferences";
import type { Selection } from "./channelsApi";

const { memberRequest } = vi.hoisted(() => ({ memberRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ memberRequest, staffRequest: vi.fn(), getAccessToken: () => null }));

let preferences: Selection[];
beforeEach(() => {
  preferences = [
    { category: "events", channels: ["email", "in_app"], email_fallback: true, available_channels: [] },
    { category: "presence", channels: ["in_app", "native_push"], email_fallback: false, available_channels: ["in_app"] },
    { category: "hardware_requests", channels: ["email", "in_app", "slack"], email_fallback: true, available_channels: ["email", "in_app"] },
  ];
  memberRequest.mockReset().mockImplementation(async (_path, init) => {
    const edits: Selection[] = JSON.parse(init.body).preferences;
    preferences = preferences.map(row => ({ ...row, ...edits.find(edit => edit.category === row.category) }));
    return { preferences };
  });
});

function mount() {
  render(<QueryClientProvider client={new QueryClient()}>
    <ChannelPreferences makerspaceId={8} preferences={preferences} connected={new Set()} member />
  </QueryClientProvider>);
}

it("omits hidden and untouched categories, including presence's unavailable default push", async () => {
  mount();
  expect(screen.queryByRole("group", { name: "Events" })).toBeNull();
  fireEvent.click(screen.getByRole("checkbox", { name: "Hardware requests: Email" }));
  fireEvent.click(screen.getByRole("button", { name: "Save choices" }));
  await waitFor(() => expect(memberRequest).toHaveBeenCalledTimes(1));
  expect(JSON.parse(memberRequest.mock.calls[0][1].body)).toEqual({ preferences: [
    { category: "hardware_requests", channels: ["in_app"], email_fallback: true },
  ] });
  expect(preferences[0].channels).toEqual(["email", "in_app"]);
  expect(preferences[1].channels).toEqual(["in_app", "native_push"]);
});

it("sends an explicit opt-out only when that category was edited", async () => {
  mount();
  fireEvent.click(screen.getByRole("checkbox", { name: "Presence: Inbox" }));
  fireEvent.click(screen.getByRole("button", { name: "Save choices" }));
  await waitFor(() => expect(memberRequest).toHaveBeenCalledTimes(1));
  expect(JSON.parse(memberRequest.mock.calls[0][1].body)).toEqual({ preferences: [
    { category: "presence", channels: [], email_fallback: false },
  ] });
});

it("saves fallback-only edits without freezing other categories' defaults", async () => {
  mount();
  const group = within(screen.getByRole("group", { name: "Hardware requests" }));
  fireEvent.click(group.getByRole("checkbox", { name: "Email me if none of these could deliver" }));
  fireEvent.click(screen.getByRole("button", { name: "Save choices" }));
  await waitFor(() => expect(memberRequest).toHaveBeenCalledTimes(1));
  expect(JSON.parse(memberRequest.mock.calls[0][1].body)).toEqual({ preferences: [
    { category: "hardware_requests", channels: ["email", "in_app"], email_fallback: false },
  ] });
});

it("does not submit categories whose edits were reverted or discarded", () => {
  mount();
  const email = screen.getByRole("checkbox", { name: "Hardware requests: Email" });
  fireEvent.click(email);
  fireEvent.click(email);
  expect(screen.getByRole("button", { name: "Save choices" })).toBeDisabled();
  fireEvent.click(email);
  fireEvent.click(screen.getByRole("button", { name: "Discard" }));
  expect(screen.getByRole("button", { name: "Save choices" })).toBeDisabled();
  expect(memberRequest).not.toHaveBeenCalled();
});
