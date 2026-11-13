import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { memberRequest } from "../../lib/api";
import { MemberNotifications } from "./MemberNotifications";
vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(), memberRequest: vi.fn() }));
vi.mock("../../lib/useLiveUpdates", () => ({ useLiveUpdates: vi.fn() }));
vi.mock("./MyNotificationSettings", () => ({ MyNotificationSettings: () => null }));
vi.mock("./PersonalInbox", () => ({ PersonalInbox: () => null }));
it("offers Firebase setup to a member only when the independent notification config is available", async () => {
  vi.mocked(memberRequest).mockResolvedValue({ configured: true, config: null });
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/member/inbox?section=channels"]}><MemberNotifications makerspaceId={8} features={["notifications.web_push"]} /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByRole("link", { name: "Set up Firebase browser notifications" })).toHaveAttribute("href", "/firebase-alerts/setup?space=8");
});

it("hides Firebase setup when that notification feature is off", () => {
  const request = vi.mocked(memberRequest); request.mockClear();
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/member/inbox?section=channels"]}><MemberNotifications makerspaceId={9} features={[]} /></MemoryRouter></QueryClientProvider>);
  expect(screen.queryByRole("link", { name: "Set up Firebase browser notifications" })).toBeNull();
  expect(request).not.toHaveBeenCalled();
});
