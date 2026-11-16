import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { PayoutDetail } from "./PayoutDetail";
import { PayoutQueue } from "./PayoutQueue";
import { MemberPayoutHistory } from "./MemberPayoutHistory";
import { MemberPayoutDetail } from "./MemberPayoutDetail";
import { payout, scope } from "./testData";
import type { PayoutDetail as Data } from "./types";
const { data, mutation } = vi.hoisted(() => ({ data: vi.fn(), mutation: vi.fn() }));
vi.mock("./api", async importOriginal => ({ ...await importOriginal<typeof import("./api")>(),
  usePayout: () => ({ data: data() }), useMemberPayout: () => ({ data: data() }),
  usePayouts: () => ({ data: { count: 1, results: [data()] } }),
  useMemberPayoutHistory: () => ({ data: { count: 1, results: [data()] } }),
  usePayoutCommand: () => ({ mutate: mutation }),
}));
afterEach(() => vi.clearAllMocks());
describe("finance and owner page entrypoints", () => {
  it("does not let the legacy canRecord prop grant any controls", () => {
    data.mockReturnValue({ ...payout, allowed_actions: [] });
    render(<PayoutDetail scope={scope} id="obligation" canRecord />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText(/Routing details hidden/)).toBeVisible();
  });
  it("uses server list controls and never selects an ineligible CSV row", () => {
    data.mockReturnValue({ ...payout, allowed_actions: ["view"] }); const open = vi.fn();
    render(<PayoutQueue scope={scope} onOpen={open} />);
    fireEvent.click(screen.getByRole("button", { name: "Review obligation" })); expect(open).toHaveBeenCalledWith("obligation");
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(screen.queryByRole("button", { name: "Preview masked CSV" })).toBeNull();
  });
  it("mounts owner history without an Events or membership gate", () => {
    data.mockReturnValue({ ...payout, allowed_actions: ["view"] }); const open = vi.fn();
    render(<MemberPayoutHistory actorId={73} onOpen={open} />);
    fireEvent.click(screen.getByRole("button", { name: "View reimbursement" })); expect(open).toHaveBeenCalledWith("obligation");
  });
  it("shows safe owner history with no finance receipts or decision snapshot", () => {
    data.mockReturnValue({ ...payout, allowed_actions: [], revisions: [{ id: 1, decision_summary: { note: "Private finance decision" } }] } as unknown as Data);
    render(<MemberPayoutDetail actorId={73} id="obligation" />);
    expect(screen.queryByText("Private finance decision")).toBeNull();
    expect(screen.queryByRole("button", { name: /receipt/i })).toBeNull();
    expect(screen.queryByLabelText("Country and payment method")).toBeNull();
  });
});
