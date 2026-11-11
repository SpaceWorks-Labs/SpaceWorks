import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemberAllowances } from "./MemberAllowances";

const { memberRequest } = vi.hoisted(() => ({ memberRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ memberRequest }));

const mount = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}>
  <MemberAllowances makerspaceId={7} />
</QueryClientProvider>);
const meter = (used: number, limit: number | null) => ({ used, limit, remaining: limit === null ? null : limit - used,
  percent: limit ? used * 100 / limit : null, level: limit && used >= limit ? "limit" : limit && used / limit >= 0.8 ? "warning" : "ok" });

beforeEach(() => { memberRequest.mockReset(); });

describe("a member's own allowances (#234 addendum 3a)", () => {
  it("shows loans, guests and day passes left", async () => {
    memberRequest.mockResolvedValue({ makerspace_id: 7, borrowing: { active_loans: meter(1, 3), items_out: meter(2, null) },
      included_hours: [], guest_passes: meter(0, 2), day_passes: [{ product_id: 1, name: "Day pass", available_today: false }] });
    mount();
    expect(await screen.findByText("What you have left")).toBeVisible();
    expect(screen.getByText("2 of 3 left")).toBeVisible();
    expect(screen.getByText("2 of 2 left")).toBeVisible();
    expect(screen.queryByText("Items out at once")).not.toBeInTheDocument(); // no cap, nothing to count down
    expect(screen.getByText("Day pass: sold out")).toBeVisible();
  });

  it("warns at the borrowing limit", async () => {
    memberRequest.mockResolvedValue({ makerspace_id: 7, borrowing: { active_loans: meter(3, 3), items_out: meter(0, null) },
      included_hours: [], guest_passes: null, day_passes: null });
    mount();
    expect(await screen.findByText("You've reached your borrowing limit.")).toBeVisible();
  });

  it("renders nothing when no section applies", async () => {
    memberRequest.mockResolvedValue({ makerspace_id: 7, borrowing: null, included_hours: [], guest_passes: null, day_passes: null });
    const { container } = mount();
    await Promise.resolve();
    expect(container).toBeEmptyDOMElement();
  });
});
