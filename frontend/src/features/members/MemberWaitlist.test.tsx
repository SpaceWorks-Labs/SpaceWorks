import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import type { WaitlistEntry } from "../inventory/waitlistApi";
import { MemberRequestWithdraw } from "./MemberRequestWithdraw";
import { MemberWaitlist } from "./MemberWaitlist";

const { member, submit } = vi.hoisted(() => ({ member: vi.fn(), submit: vi.fn() }));
vi.mock("../../lib/api", () => ({ memberRequest: member, staffRequest: vi.fn() }));
vi.mock("../inventory/api", () => ({ submitPublicRequest: submit }));

const waiting: WaitlistEntry = { id: 1, product: 4, product_name: "Drill", quantity: 1, status: "waiting", position: 2, offered_at: null, offer_expires_at: null, created_at: "2026-11-01T10:00:00Z" };
const offered: WaitlistEntry = { ...waiting, id: 2, product: 5, product_name: "Saw", quantity: 2, status: "offered", position: null, offered_at: "2026-11-02T10:00:00Z", offer_expires_at: "2026-11-03T10:00:00Z" };

beforeEach(() => {
  member.mockReset(); submit.mockReset();
  member.mockImplementation(async (_path: string, init?: RequestInit) => init?.method === "POST" ? { ...waiting, status: "claimed" } : [waiting, offered]);
});

const wrap = (node: React.ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{node}</QueryClientProvider>);

it("lists waiting places with their position and offers with their hold deadline", async () => {
  wrap(<MemberWaitlist makerspaceId={7} makerspaceSlug="forge" />);
  expect(await screen.findByText("Drill ×1")).toBeInTheDocument();
  expect(screen.getByText("Number 2 in line")).toBeInTheDocument();
  expect(screen.getByText(/Held for you until/)).toBeInTheDocument();
  expect(member).toHaveBeenCalledWith("/member/makerspaces/7/waitlist");
});

it("leaves a waitlist", async () => {
  wrap(<MemberWaitlist makerspaceId={7} makerspaceSlug="forge" />);
  await screen.findByText("Drill ×1");
  fireEvent.click(screen.getAllByRole("button", { name: "Leave" })[0]);
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Leave waitlist" }));
  await waitFor(() => expect(member).toHaveBeenCalledWith("/member/makerspaces/7/waitlist/1/leave", { method: "POST", body: JSON.stringify({}) }));
});

it("requests an offered item with the waitlist entry id", async () => {
  submit.mockResolvedValue({ public_token: "t", status: "pending_approval" });
  wrap(<MemberWaitlist makerspaceId={7} makerspaceSlug="forge" />);
  await screen.findByText("Saw ×2");
  fireEvent.click(screen.getByRole("button", { name: "Request it" }));
  fireEvent.change(screen.getByLabelText("What do you need it for?"), { target: { value: "Cutting boards" } });
  fireEvent.click(screen.getByRole("button", { name: "Send request" }));
  await waitFor(() => expect(submit).toHaveBeenCalledWith("forge", { requested_for: "Cutting boards", items: [{ product_id: 5, quantity: 2 }], waitlist_entry_id: 2 }));
  expect(await screen.findByText("Request sent. Staff will review it.")).toBeInTheDocument();
});

it("renders nothing when the member is not waiting for anything", async () => {
  member.mockResolvedValue([]);
  const { container } = wrap(<MemberWaitlist makerspaceId={7} makerspaceSlug="forge" />);
  await waitFor(() => expect(member).toHaveBeenCalled());
  expect(container).toBeEmptyDOMElement();
});

it("withdraws a request after confirming", async () => {
  member.mockResolvedValue({ id: 9, status: "cancelled", closed_at: "2026-11-02T10:00:00Z" });
  wrap(<MemberRequestWithdraw makerspaceId={7} makerspaceSlug="forge" requestId={9} />);
  fireEvent.click(screen.getByRole("button", { name: "Withdraw" }));
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Withdraw request" }));
  await waitFor(() => expect(member).toHaveBeenCalledWith("/member/makerspaces/7/requests/9/withdraw", { method: "POST", body: JSON.stringify({}) }));
  expect(await screen.findByText("Request withdrawn.")).toBeInTheDocument();
});
