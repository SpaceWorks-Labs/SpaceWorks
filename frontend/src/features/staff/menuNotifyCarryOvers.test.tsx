import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { paymentAccess } from "./paymentAccess";
import type { PaymentRow } from "./paymentsApi";
import { useDomainSettingsDialog } from "./useDomainSettingsDialog";
import { EventsPanel } from "./EventsPanel";
import { NotificationInbox } from "./panels/NotificationInbox";
import { MemberNotifications } from "../notifications/MemberNotifications";
import type { Makerspace } from "./panels/shared";

const { staffRequest, memberRequest } = vi.hoisted(() => ({ staffRequest: vi.fn(), memberRequest: vi.fn() }));
// EventsPanel now also asks isSurfaceOff (module-off 404s); nothing here errors.
vi.mock("../../lib/api", () => ({ staffRequest, memberRequest, getAccessToken: () => null, StructuredApiError: class extends Error {}, isSurfaceOff: () => false }));
vi.mock("./DomainSettingsSection", () => ({ DomainSettingsSection: ({ domain }: { domain: string }) => <p>{domain} switches</p> }));
vi.mock("./eventsApi", () => ({
  useEvents: () => ({ data: { count: 0, previous: null, next: null, results: [] }, isLoading: false, error: null, refetch: vi.fn() }),
  useCreateEvent: () => ({ mutate: vi.fn(), isPending: false }),
}));
vi.mock("./eventSeriesApi", () => ({
  useEventSeriesList: () => ({ data: { count: 0, results: [] }, isLoading: false, error: null, refetch: vi.fn() }),
  useCreateEventSeries: () => ({ mutate: vi.fn(), isPending: false }),
}));
vi.mock("./EventCollaborationReview", () => ({ useEventCollaborationReview: () => ({}) }));
vi.mock("./ListViewControls", () => ({ ListViewControls: () => null }));
vi.mock("../notifications/PersonalInbox", () => ({
  PersonalInbox: ({ announcement, overflow }: { announcement?: { label: string; onClick: () => void }; overflow?: { label: string }[] }) => <>
    {announcement ? <button onClick={announcement.onClick}>{announcement.label}</button> : null}
    <p>overflow: {(overflow ?? []).map(action => action.label).join(",")}</p></>,
}));
vi.mock("../notifications/MyNotificationSettings", () => ({ MyNotificationSettings: ({ member }: { member?: boolean }) => <p>my settings {member ? "member" : "staff"}</p> }));
vi.mock("../../lib/useLiveUpdates", () => ({ useLiveUpdates: () => undefined }));

const wrap = (ui: React.ReactNode, url = "/") => render(<QueryClientProvider client={new QueryClient()}>
  <MemoryRouter initialEntries={[url]}>{ui}</MemoryRouter></QueryClientProvider>);
const row = (subject_type: PaymentRow["subject_type"]) => ({ subject_type, status: "pending" }) as PaymentRow;

beforeEach(() => { staffRequest.mockReset(); memberRequest.mockReset(); });

describe("payment access follows the backend subject authority", () => {
  it("lets member managers settle membership admission fees", () => {
    expect(paymentAccess(["manage_members"], false, row("membership_request"))).toMatchObject({ record: true, waive: true });
    expect(paymentAccess(["manage_makerspace"], false, row("membership_request"))).toMatchObject({ record: false, waive: false });
    expect(paymentAccess(["manage_makerspace"], false, row("membership_term"))).toMatchObject({ waive: true });
  });
});

describe("domain settings dialogs", () => {
  function Probe({ extra }: { extra?: React.ReactNode }) {
    const settings = useDomainSettingsDialog(4, "inventory", true, extra);
    return <><button onClick={settings.actions[0].onClick}>{settings.actions[0].label}</button>{settings.dialog}</>;
  }
  it("renders the domain's own editors under the switches (Inventory: loan policy)", () => {
    wrap(<Probe extra={<p>Loan policy editor</p>} />);
    fireEvent.click(screen.getByRole("button", { name: "Inventory settings" }));
    expect(screen.getByText("inventory switches")).toBeVisible();
    expect(screen.getByText("Loan policy editor")).toBeVisible();
  });

  it("mounts the Events domain settings in the Events console", () => {
    wrap(<EventsPanel makerspaceId={3} />);
    fireEvent.click(screen.getAllByRole("button", { name: /More actions|Event settings/ })[0]);
    fireEvent.click(screen.getByRole("menuitem", { name: "Event settings" }));
    expect(screen.getByRole("dialog", { name: "Event settings" })).toBeVisible();
    expect(screen.getByText("events switches")).toBeVisible();
  });
});

describe("personal notification channel entry points", () => {
  const space = { id: 7, name: "Forge", enabled_modules: ["notifications"], enabled_features: [] } as unknown as Makerspace;
  it("gives staff a My channels dialog in the inbox", () => {
    wrap(<NotificationInbox makerspace={space} />);
    fireEvent.click(screen.getByRole("button", { name: "My channels" }));
    expect(screen.getByRole("dialog", { name: "My notification channels" })).toBeVisible();
    expect(screen.getByText("my settings staff")).toBeVisible();
  });

  it("keeps the announcement primary and moves My channels to the overflow", () => {
    wrap(<NotificationInbox makerspace={{ ...space, enabled_features: ["membership.broadcasts"] }} canManageMembers />);
    expect(screen.getByRole("button", { name: "Send announcement" })).toBeInTheDocument();
    expect(screen.getByText("overflow: My channels")).toBeInTheDocument();
  });

  it("keeps personal channels available without the inbox module", () => {
    wrap(<NotificationInbox makerspace={{ ...space, enabled_modules: [] }} />);
    fireEvent.click(screen.getByRole("button", { name: "My channels" }));
    expect(screen.getByRole("dialog", { name: "My notification channels" })).toBeVisible();
    expect(screen.getByText("my settings staff")).toBeVisible();
  });

  it("gives members a Channels tab, opened directly after a provider sign-in", () => {
    wrap(<MemberNotifications makerspaceId={7} features={[]} />, "/?state=signed-state&code=x");
    expect(screen.getByRole("tab", { name: "Channels" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("my settings member")).toBeVisible();
  });

  it("does not open channel completion for an unbound challenge query", () => {
    wrap(<MemberNotifications makerspaceId={7} features={["notifications.member_inbox"]} />, "/?notify_challenge=5&code=x");
    expect(screen.getByRole("tab", { name: "Channels" })).toHaveAttribute("aria-selected", "false");
    expect(screen.queryByText("my settings member")).toBeNull();
  });
});
