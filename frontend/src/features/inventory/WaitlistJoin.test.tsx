import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import type { Product } from "../../types/inventory";
import { ExpectedBack, formatExpectedBack } from "./ExpectedBack";
import { WaitlistJoin } from "./WaitlistJoin";

const { member, token } = vi.hoisted(() => ({ member: vi.fn(), token: vi.fn() }));
vi.mock("../../lib/api", () => ({ memberRequest: member, staffRequest: vi.fn(), getAccessToken: token }));

const out: Product = { id: 4, name: "Drill", description: "", availability: { mode: "status_only", label: "Unavailable" }, expected_back_on: "2026-11-14" };

beforeEach(() => { member.mockReset(); token.mockReset(); token.mockReturnValue("member-token"); });

function renderJoin(product: Product = out, features = ["loans.waitlist"]) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
    <WaitlistJoin makerspaceId={7} product={product} features={features} /></QueryClientProvider>);
}

it("shows Back around <date> only for an item that is out", () => {
  const { rerender } = render(<ExpectedBack product={out} />);
  expect(screen.getByText(/Back around/)).toHaveTextContent(formatExpectedBack("2026-11-14"));
  expect(screen.getByText(/Back around/).querySelector("time")).toHaveAttribute("datetime", "2026-11-14");
  rerender(<ExpectedBack product={{ ...out, availability: { mode: "status_only", label: "Available" } }} />);
  expect(screen.queryByText(/Back around/)).not.toBeInTheDocument();
  rerender(<ExpectedBack product={{ ...out, expected_back_on: null }} />);
  expect(screen.queryByText(/Back around/)).not.toBeInTheDocument();
});

it("joins the waitlist for a signed-in member and says where they are in line", async () => {
  member.mockResolvedValue({ id: 1, product: 4, product_name: "Drill", quantity: 1, status: "waiting", position: 3, offered_at: null, offer_expires_at: null, created_at: "" });
  renderJoin();
  fireEvent.click(screen.getByRole("button", { name: "Join the waitlist" }));
  await waitFor(() => expect(member).toHaveBeenCalledWith("/member/makerspaces/7/waitlist", { method: "POST", body: JSON.stringify({ product_id: 4, quantity: 1 }) }));
  expect(await screen.findByRole("status")).toHaveTextContent("You're number 3 in line for Drill.");
});

it("shows the server's 'request it instead' refusal", async () => {
  member.mockRejectedValue(new Error("This item is available now; request it instead."));
  renderJoin();
  fireEvent.click(screen.getByRole("button", { name: "Join the waitlist" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("request it instead");
});

it("stays hidden when signed out, switched off or the item is available", () => {
  token.mockReturnValue(null);
  renderJoin();
  expect(screen.queryByRole("button", { name: "Join the waitlist" })).not.toBeInTheDocument();
  token.mockReturnValue("member-token");
  renderJoin(out, []);
  expect(screen.queryByRole("button", { name: "Join the waitlist" })).not.toBeInTheDocument();
  renderJoin({ ...out, availability: { mode: "status_only", label: "Limited" } });
  expect(screen.queryByRole("button", { name: "Join the waitlist" })).not.toBeInTheDocument();
});
