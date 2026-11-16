import { render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { MemberNotifications } from "./MemberNotifications";

vi.mock("../../lib/useLiveUpdates", () => ({ useLiveUpdates: () => {} }));
vi.mock("./MyNotificationSettings", () => ({ MyNotificationSettings: () => <div>OAuth return settings</div> }));
vi.mock("./PersonalInbox", () => ({ PersonalInbox: () => <div>Inbox</div> }));
vi.mock("./PreferenceCentre", () => ({ PreferenceCentre: () => <div>Preferences</div> }));
vi.mock("./AnnouncementFeed", () => ({ AnnouncementFeed: () => null }));

function SearchParams() {
  return <output data-testid="search-params">{useLocation().search}</output>;
}

it("opens channels for a state-only OAuth return even when another section was registered", () => {
  render(<MemoryRouter initialEntries={["/?section=preferences&code=provider-code&state=signed"]}>
    <MemberNotifications makerspaceId={8} features={["notifications.member_inbox", "notifications.member_preferences"]} />
    <SearchParams />
  </MemoryRouter>);
  expect(screen.getByText("OAuth return settings")).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Channels" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByTestId("search-params")).toHaveTextContent("?section=preferences&code=provider-code&state=signed");
});

it.each(["/", "/?section=notices", "/?section=announcements"])(
  "falls back to Channels and hides inbox tabs at %s when the inbox is off",
  path => {
    render(<MemoryRouter initialEntries={[path]}>
      <MemberNotifications makerspaceId={8} features={["membership.broadcasts", "notifications.member_preferences"]} />
    </MemoryRouter>);
    expect(screen.queryByRole("tab", { name: "Notices" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Announcements" })).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Channels" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("OAuth return settings");
  },
);

it("still defaults to Notices while the inbox is on", () => {
  render(<MemoryRouter><MemberNotifications makerspaceId={8} features={["notifications.member_inbox"]} /></MemoryRouter>);
  expect(screen.getByRole("tab", { name: "Notices" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tabpanel")).toHaveTextContent("Inbox");
});
