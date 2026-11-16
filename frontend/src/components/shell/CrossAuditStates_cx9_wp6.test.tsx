import { fireEvent, render, screen, within } from "@testing-library/react";
import { Circle } from "lucide-react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { NoStaffRoleScreen } from "../../features/staff/StaffGateScreens";
import { chooseTheme } from "../../lib/theme";
import { EmptyState, ErrorBlock, Spinner } from "../ui";
import { AppShell } from "./AppShell";
import type { AppShellProps } from "./types";

// area_frontend_shell: production shell and state primitives, not a mocked route.
afterEach(() => { chooseTheme("light"); localStorage.clear(); });
const props = (): Omit<AppShellProps, "children"> => ({
  variant: "staff", compactNav: "drawer", activeKey: "reports",
  nav: [{ key: "work", items: [{ key: "reports", label: "Reports", href: "/admin/reports", icon: Circle }] }],
  user: { name: "Casey", role: "Space Manager", menu: [] },
});

it.each(["light", "dark"] as const)("%s shell replaces loading/error/empty states and retains keyboard navigation", (theme) => {
  chooseTheme(theme);
  const retry = vi.fn();
  const view = render(<MemoryRouter><AppShell {...props()}><Spinner label="Loading reports" /></AppShell></MemoryRouter>);
  expect(screen.getByRole("status", { name: "Loading reports" })).toBeInTheDocument();
  expect(document.documentElement.classList.contains("dark")).toBe(theme === "dark");
  view.rerender(<MemoryRouter><AppShell {...props()}><ErrorBlock error={new Error("Temporary report failure")} onRetry={retry} /></AppShell></MemoryRouter>);
  expect(screen.queryByRole("status", { name: "Loading reports" })).toBeNull();
  expect(screen.getByRole("alert")).toHaveTextContent("Temporary report failure");
  const button = within(screen.getByRole("alert")).getByRole("button", { name: "Retry" });
  button.focus();
  expect(button).toHaveFocus();
  fireEvent.click(button);
  expect(retry).toHaveBeenCalledTimes(1);
  view.rerender(<MemoryRouter><AppShell {...props()}><EmptyState message="No reports in this range" /></AppShell></MemoryRouter>);
  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.getByRole("status")).toHaveTextContent("No reports in this range");
  const nav = screen.getByRole("navigation", { name: "Staff sections" });
  const link = within(nav).getByRole("link", { name: "Reports" });
  expect(link).toHaveAttribute("aria-current", "page");
  link.focus();
  fireEvent.keyDown(link, { key: "Home" });
  expect(link).toHaveFocus();
});

it("the no-role screen keeps the member exit and sign-out usable without exposing a staff navigation", () => {
  const signOut = vi.fn();
  render(<NoStaffRoleScreen memberHref="/m/wp6/member" onSignOut={signOut} />);
  expect(screen.getByRole("heading", { name: "You don't have a staff role yet" })).toBeVisible();
  expect(screen.getByRole("link", { name: "Go to your member area" })).toHaveAttribute("href", "/m/wp6/member");
  const escape = screen.getByRole("button", { name: "Sign out" });
  escape.focus();
  expect(escape).toHaveFocus();
  fireEvent.click(escape);
  expect(signOut).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("navigation", { name: "Staff sections" })).toBeNull();
});
