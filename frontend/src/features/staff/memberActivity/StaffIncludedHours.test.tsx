import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { StaffIncludedHours } from "./StaffIncludedHours";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...(await original<object>()), staffRequest: api.staffRequest }));

const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);
const pool = { kind: "booking" as const, term_id: 4, plan_name: "Studio plan", term_starts_at: "2026-11-01T00:00:00Z",
  term_ends_at: "2026-12-01T00:00:00Z", allowance_minutes: 600, used_minutes: 150, remaining_minutes: 450 };

describe("StaffIncludedHours (C26)", () => {
  beforeEach(() => { api.staffRequest.mockReset(); });

  it("reads the member's balance and shows what is left in each pool", async () => {
    api.staffRequest.mockResolvedValue({ member_id: 21, enabled: true, pools: [pool, { ...pool, kind: "machine", allowance_minutes: 120, used_minutes: 120, remaining_minutes: 0 }] });
    wrap(<StaffIncludedHours makerspaceId={4} userId={21} />);
    expect(await screen.findByText("7.5 of 10 h left this term")).toBeInTheDocument();
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspace/4/members/21/included-hours", expect.anything());
    expect(screen.getByText("Room bookings")).toBeInTheDocument();
    expect(screen.getByText("Machine time")).toBeInTheDocument();
    expect(screen.getByText("0 of 2 h left this term")).toBeInTheDocument();
  });

  it("disappears while bookings or membership is off, or the plan includes no hours", async () => {
    api.staffRequest.mockResolvedValue({ member_id: 21, enabled: false, pools: [pool] });
    const off = wrap(<StaffIncludedHours makerspaceId={4} userId={21} />);
    await vi.waitFor(() => expect(api.staffRequest).toHaveBeenCalled());
    expect(off.container).toBeEmptyDOMElement();
    off.unmount();
    api.staffRequest.mockResolvedValue({ member_id: 21, enabled: true, pools: [{ ...pool, allowance_minutes: 0, remaining_minutes: 0 }] });
    const none = wrap(<StaffIncludedHours makerspaceId={4} userId={21} />);
    await vi.waitFor(() => expect(api.staffRequest).toHaveBeenCalledTimes(2));
    expect(none.container).toBeEmptyDOMElement();
  });

  it("shows nothing, not a zero balance, when the server refuses the viewer", async () => {
    api.staffRequest.mockRejectedValue(new StructuredApiError(404, { detail: "Not found." }));
    const { container } = wrap(<StaffIncludedHours makerspaceId={4} userId={21} />);
    await vi.waitFor(() => expect(api.staffRequest).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
