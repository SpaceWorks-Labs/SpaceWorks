import { fireEvent, render as rtlRender, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// Screens now read query-backed switches (help-centre bootstrap, #184 charge flags), so every render needs a client.
function render(ui: Parameters<typeof rtlRender>[0], options?: Parameters<typeof rtlRender>[1]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children?: Parameters<typeof rtlRender>[0] }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return rtlRender(ui, { wrapper, ...options });
}
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { MEMBER_TABS, MemberPortalTabs, memberTabLabel, memberTabs, useMemberTab } from "./MemberPortalTabs";
import { expectNoA11yViolations } from "../../test/axe";

const modules = ["membership", "request_workflow", "bookings", "events"];
function Harness({ enabled = modules }: { enabled?: string[] }) {
  const active = useMemberTab(enabled); const location = useLocation(); const navigate = useNavigate();
  return <><MemberPortalTabs modules={enabled} active={active} user={{ name: "Member", menu: [], onSignOut: () => {} }}><h1>{active} content</h1><button onClick={() => navigate(-1)}>Back</button></MemberPortalTabs><output>{location.pathname}</output></>;
}
const nav = () => within(screen.getByRole("navigation", { name: "Member portal" }));
it.each(["/member", "/m/lab/member", "/m/member/member", "/m/member-tools/member"])("member URL links and browser Back work under %s", base => {
  render(<MemoryRouter initialEntries={[`${base}/bookings`]}><Harness /></MemoryRouter>);
  expect(nav().getByRole("link", { name: "Bookings" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("main")).toHaveAttribute("id", "main-content"); expect(screen.getByRole("main")).toHaveAttribute("tabindex", "-1");
  fireEvent.click(nav().getByRole("link", { name: "Events" })); expect(screen.getByText(`${base}/events`)).toBeInTheDocument();
  expect(screen.queryByText("bookings content")).toBeNull(); fireEvent.click(screen.getByText("Back")); expect(screen.getByText("bookings content")).toBeInTheDocument();
});
it("member sidebar uses named nav links with normal Tab stops, selected page and a skip target", async () => {
  const view = render(<MemoryRouter initialEntries={["/m/lab/member"]}><Harness /></MemoryRouter>);
  const links = nav().getAllByRole("link"); expect(links.every(link => link.tabIndex === 0)).toBe(true);
  expect(links.filter(link => link.getAttribute("aria-current") === "page")).toHaveLength(1);
  expect(nav().getByRole("link", { name: "Home" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute("href", "#main-content");
  expect(screen.getByRole("main").querySelector("nav")).toBeNull();
  fireEvent.click(nav().getByRole("link", { name: "Account" })); expect(screen.getByText("/m/lab/member/account-portal")).toBeInTheDocument();
  await expectNoA11yViolations(view.container);
});
it("member gating keeps account-only payments and hides module-dependent destinations", () => {
  render(<MemoryRouter initialEntries={["/m/lab/member/loans"]}><Harness enabled={[]} /></MemoryRouter>);
  expect(nav().getAllByRole("link").map(link => link.textContent)).toEqual(["Home", "Payments", "Account"]);
  expect(screen.getByText("overview content")).toBeInTheDocument(); fireEvent.click(nav().getByRole("link", { name: "Payments" })); expect(screen.getByText("payments content")).toBeInTheDocument();
});
it("invalid member segments never enter the portal base", () => {
  render(<MemoryRouter initialEntries={["/m/member/member/member"]}><Harness /></MemoryRouter>);
  fireEvent.click(nav().getByRole("link", { name: "Account" })); expect(screen.getByText("/m/member/member/account-portal")).toBeInTheDocument();
});
it("member mobile More exposes every destination with Escape focus restoration", async () => {
  // The Inbox destination is the notifications module's surface (#183B, 8bcd7318), so this space runs it.
  render(<MemoryRouter><Harness enabled={[...modules, "notifications"]} /></MemoryRouter>);
  const more = screen.getByRole("button", { name: "More" }); more.focus(); fireEvent.click(more);
  const drawer = screen.getByRole("dialog", { name: "Navigation" }); expect(within(drawer).getByRole("link", { name: "Inbox" })).toBeInTheDocument();
  fireEvent.keyDown(document, { key: "Escape" }); expect(screen.queryByRole("dialog")).toBeNull(); expect(more).toHaveFocus();
});

// Role-screen audit 0.12.0: the member-side roles x module states, pinned on the tab list.
describe("member portal per role and module state", () => {
  const ALL = ["membership", "request_workflow", "bookings", "events", "notifications", "member_accounts"];
  const LENDING = ["loans.enabled"];
  it.each([
    ["active member, everything on", ALL, LENDING, ["overview", "loans", "bookings", "events", "payments", "inbox", "account"]],
    // Account-only borrower: membership off, member_accounts on. Loans and event history are
    // reached from Home > Your history; payments and account stay.
    ["account-only borrower", ALL.filter(key => key !== "membership"), LENDING, ["overview", "bookings", "payments", "account"]],
    ["lending switched off", ALL, [], ["overview", "bookings", "events", "payments", "inbox", "account"]],
    ["bookings and events off", ["membership", "request_workflow", "notifications"], LENDING, ["overview", "loans", "payments", "inbox", "account"]],
  ])("%s", (_name, modules, features, expected) => {
    expect(memberTabs(modules, features)).toEqual(expected);
  });

  it("keeps the module-only rule for callers without a capability list", () => {
    expect(memberTabs(ALL)).toContain("loans");
  });

  it("names every tab through the translated label map", () => {
    expect(MEMBER_TABS.map(memberTabLabel)).toEqual(["Home", "Loans", "Bookings", "Events", "Payments", "Inbox", "Account"]);
  });

  it("gives a signed-out visitor Home only: every other tab is their own account's data", () => {
    render(<MemoryRouter initialEntries={["/m/lab/member/payments"]}>
      <MemberPortalTabs modules={ALL} features={LENDING} active="payments" user={{ name: "Not signed in", menu: [] }}><h1>content</h1></MemberPortalTabs>
    </MemoryRouter>);
    expect(nav().getAllByRole("link").map(link => link.textContent)).toEqual(["Home"]);
  });

  it("hides the Loans tab and falls back to Home when lending is off", () => {
    function Lending() {
      const active = useMemberTab(ALL, []);
      return <MemberPortalTabs modules={ALL} features={[]} active={active} user={{ name: "Member", menu: [], onSignOut: () => {} }}><h1>{active} content</h1></MemberPortalTabs>;
    }
    render(<MemoryRouter initialEntries={["/m/lab/member/loans"]}><Lending /></MemoryRouter>);
    expect(screen.getByText("overview content")).toBeInTheDocument();
    expect(nav().queryByRole("link", { name: "Loans" })).toBeNull();
  });
});
