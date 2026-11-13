import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { AreaConsoleLink, withSettingsOpen } from "./SettingsAreaConsoleLink";
import { useDomainSettingsDialog } from "./useDomainSettingsDialog";

vi.mock("./DomainSettingsSection", () => ({ DomainSettingsSection: () => <p>Area switches</p> }));
vi.mock("./areaPayments/AreaPricingSection", () => ({ AreaPricingSection: () => null }));
vi.mock("../stats/settings/PublicStatsSettingsPanel", () => ({ PublicStatsSettingsPanel: () => null }));

function Page({ allowed = true }: { allowed?: boolean }) {
  const settings = useDomainSettingsDialog(7, "events", allowed);
  return <>{settings.actions.map(action => <button key={action.label} onClick={action.onClick}>{action.label}</button>)}{settings.dialog}</>;
}

afterEach(() => { window.history.replaceState(null, "", "/"); });

// Decision 255: Settings › Areas › Events links to the Events page with ?settings=open.
it("opens the area settings dialog on arrival from a settings link and drops the flag on close", () => {
  window.history.replaceState(null, "", "/m/lab/admin/events?settings=open&context=person");
  render(<Page />);
  expect(screen.getByRole("dialog", { name: "Event settings" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Close dialog" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(window.location.search).toBe("?context=person");
});

it("stays closed without the flag and for someone without the area's permission", () => {
  window.history.replaceState(null, "", "/m/lab/admin/events");
  const { unmount } = render(<Page />);
  expect(screen.queryByRole("dialog")).toBeNull();
  unmount();
  window.history.replaceState(null, "", "/m/lab/admin/events?settings=open");
  render(<Page allowed={false} />);
  expect(screen.queryByRole("dialog")).toBeNull();
});

it("links a settings page to its area's own settings only when the actor may open that area", () => {
  expect(withSettingsOpen("/admin/events")).toBe("/admin/events?settings=open");
  expect(withSettingsOpen("/admin/events?context=platform")).toBe("/admin/events?context=platform&settings=open");
  const href = (tab: string) => `/m/lab/admin/${tab}`;
  const { unmount } = render(<MemoryRouter><AreaConsoleLink section="materials" allowedTabs={["machines"]} tabHref={href} /></MemoryRouter>);
  expect(screen.getByRole("link", { name: "Open Machines" })).toHaveAttribute("href", "/m/lab/admin/machines");
  unmount();
  render(<MemoryRouter><AreaConsoleLink section="events" allowedTabs={["bookings"]} tabHref={href} /></MemoryRouter>);
  expect(screen.queryByRole("link")).toBeNull();
});
