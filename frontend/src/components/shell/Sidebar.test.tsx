import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Circle } from "lucide-react";
import { beforeEach, expect, it, vi } from "vitest";
import { AppShell } from "./AppShell";
import { Sidebar } from "./Sidebar";
import { sidebarSections } from "../../features/staff/sidebarSections";
import { staffTabPath } from "../../features/staff/staffTabs";
import { getStaffAccess } from "../../features/staff/staffAccess";
import { expectNoA11yViolations } from "../../test/axe";
import type { AppShellProps } from "./types";
import { spaceManagerActions } from "../../test/staffActor";

const user = { name: "Casey", role: "Manager", menu: [{ label: "Account & two-step sign-in", href: "/mfa" }], onSignOut: vi.fn() };
const item = (key: string) => ({ key, label: key, href: `/admin/${key}`, icon: Circle });
function props(): AppShellProps { return { variant: "staff", compactNav: "drawer", nav: [{ key: "desk", items: [item("Items"), { ...item("Inbox"), badge: 3, badgeLabel: "unread" }] }], activeKey: "Items", user, children: <h1>Inventory</h1> }; }
beforeEach(() => { localStorage.clear(); vi.clearAllMocks(); });
it("preserves named landmark, one current page, labelled icons and unread accessible name", async () => {
  const view = render(<MemoryRouter><AppShell {...props()} /></MemoryRouter>);
  const nav = screen.getByRole("navigation", { name: "Staff sections" });
  expect(within(nav).getByRole("link", { name: "Items" })).toHaveAttribute("aria-current", "page");
  expect(within(nav).getByRole("link", { name: "Inbox 3 unread" })).toHaveTextContent("3");
  expect(within(nav).getAllByRole("link").every(link => link.querySelector("svg") && link.textContent)).toBe(true);
  await expectNoA11yViolations(view.container);
});
it("denied active key leaves no selected nav item", () => { const view = render(<MemoryRouter><Sidebar {...props()} activeKey="" /></MemoryRouter>); expect(view.container.querySelector('[aria-current="page"]')).toBeNull(); });
it("names every destination, including nested and badged links", () => {
  render(<MemoryRouter><Sidebar {...props()} nav={[{ key: "desk", items: [
    item("Requests"), { ...item("Inbox"), badge: 1, badgeLabel: "unread" },
    { ...item("Items"), children: [item("Categories")] },
  ] }]} /></MemoryRouter>);
  const nav = screen.getByRole("navigation", { name: "Staff sections" });
  for (const label of ["Requests", "Inbox 1 unread", "Items", "Categories"]) {
    expect(within(nav).getByRole("link", { name: label })).toHaveAccessibleName(label);
  }
});
it("keeps visible search and capped badge text in their accessible names", () => {
  const onOpen = vi.fn();
  render(<MemoryRouter><Sidebar {...props()} search={{ label: "Search and commands", shortcut: "mod+k", onOpen }}
    nav={[{ key: "desk", items: [{ ...item("Inbox"), badge: 123, badgeLabel: "unread" }] }]} /></MemoryRouter>);
  const search = screen.getByRole("button", { name: "Search and commands Ctrl/⌘ K" });
  expect(search).toHaveTextContent("Search and commands");
  fireEvent.click(search);
  expect(onOpen).toHaveBeenCalledOnce();
  const inbox = screen.getByRole("link", { name: "Inbox 99+ (123 unread)" });
  expect(inbox).toHaveTextContent("Inbox 99+");
});
it("Escape closes a user disclosure and restores its trigger", () => {
  render(<MemoryRouter><Sidebar {...props()} /></MemoryRouter>);
  const trigger = screen.getByRole("button", { name: "Casey Manager" }); fireEvent.click(trigger);
  const signOut = screen.getByRole("button", { name: "Sign out" }); signOut.focus(); fireEvent.keyDown(signOut, { key: "Escape" });
  expect(screen.queryByRole("button", { name: "Sign out" })).toBeNull(); expect(trigger).toHaveFocus();
});
it("Escape closes mobile drawer and restores menu focus; collapsed contents unmount", async () => {
  render(<MemoryRouter><AppShell {...props()} /></MemoryRouter>);
  const trigger = screen.getByRole("button", { name: "Open navigation, 3 need attention" }); trigger.focus(); fireEvent.click(trigger);
  expect(screen.getByRole("dialog", { name: "Navigation" })).toBeInTheDocument();
  fireEvent.keyDown(document, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull()); expect(trigger).toHaveFocus();
});
it("More unmounts hidden links, persists per user, and auto-expands for the active route", () => {
  const section = { key: "inventory", label: "Inventory", items: [item("a"), item("b"), item("c"), item("d")], more: [item("hidden")] };
  const view = render(<MemoryRouter><Sidebar {...props()} nav={[section]} /></MemoryRouter>);
  expect(screen.queryByRole("link", { name: "hidden" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /More/ })); expect(screen.getByRole("link", { name: "hidden" })).toBeInTheDocument();
  expect(localStorage.getItem("sidebar:Casey:inventory")).toBe("open");
  fireEvent.click(screen.getByRole("button", { name: /More/ })); expect(screen.queryByRole("link", { name: "hidden" })).toBeNull();
  view.rerender(<MemoryRouter><Sidebar {...props()} nav={[section]} activeKey="hidden" /></MemoryRouter>);
  expect(screen.getByRole("link", { name: "hidden" })).toHaveAttribute("aria-current", "page");
});
it("full-permission tenant staff at 1280x600 keeps every nav destination keyboard-focusable in the sole scroller", () => {
  vi.stubGlobal("innerWidth", 1280); vi.stubGlobal("innerHeight", 600);
  const scroll = vi.fn(); const previous = HTMLElement.prototype.scrollIntoView; HTMLElement.prototype.scrollIntoView = scroll;
  const permitted = getStaffAccess(spaceManagerActions, false, false).allowedTabs;
  const nav = sidebarSections(permitted, "settings");
  const view = render(<MemoryRouter><Sidebar {...props()} nav={nav} activeKey="settings" /></MemoryRouter>);
  for (const more of screen.getAllByRole("button", { name: /More/ })) fireEvent.click(more);
  const region = screen.getByRole("navigation", { name: "Staff sections" });
  const links = within(region).getAllByRole("link");
  expect(region).toHaveClass("overflow-y-auto", "min-h-0", "flex-1");
  // "My channels" is a personal setting reached from the account menu, not the sidebar (0.12.0 row 10).
  const destinations = permitted.filter(key => key !== "channels").map(key => staffTabPath(key, false));
  expect(links.map(link => link.getAttribute("href"))).toEqual(expect.arrayContaining(destinations));
  expect(links.map(link => link.getAttribute("href"))).not.toContain(staffTabPath("channels", false));
  for (const link of links) { link.focus(); fireEvent.focus(link); expect(link).toHaveFocus(); expect(link.tabIndex).toBe(0); expect(link.closest("nav")).toBe(region); }
  expect(scroll).toHaveBeenCalledWith({ block: "nearest" });
  view.unmount(); HTMLElement.prototype.scrollIntoView = previous; vi.unstubAllGlobals();
});
it("arrow, Home and End keys move focus between nav links without touching tab order", () => {
  render(<MemoryRouter><Sidebar {...props()} nav={[{ key: "desk", items: [item("a"), item("b"), item("c")] }]} /></MemoryRouter>);
  const [a, b, c] = screen.getAllByRole("link");
  a.focus(); fireEvent.keyDown(a, { key: "ArrowDown" }); expect(b).toHaveFocus();
  fireEvent.keyDown(b, { key: "End" }); expect(c).toHaveFocus();
  fireEvent.keyDown(c, { key: "ArrowDown" }); expect(a).toHaveFocus();
  fireEvent.keyDown(a, { key: "ArrowUp" }); expect(c).toHaveFocus();
  fireEvent.keyDown(c, { key: "Home" }); expect(a).toHaveFocus();
  expect([a, b, c].map(link => link.tabIndex)).toEqual([0, 0, 0]);
});
